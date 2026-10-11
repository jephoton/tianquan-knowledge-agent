"""Tests for the M5 tamper-evident audit trail.

Run with: python -m pytest tests/test_m5_audit.py -v

Covers:
- Hash-chain construction and clean verification.
- Tamper detection: mutating a field, breaking a link, reordering.
- INV4 (EveryDecisionAudited): every pipeline decision yields one event.
- Audit query API (Demo 4): filter by user / resource-substring / decision.
- Canonical serialization determinism.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone, timedelta

from backend.models import Action, Decision, DecisionResult
from backend.audit.event_schema import AuditEvent, event_from_decision
from backend.audit.hash_chain import HashChain, GENESIS_HASH, compute_hash
from backend.audit.audit_query import AuditQuery, AuditQueryEngine

from backend.auth.identity import IdentityStore
from backend.connectors.confluence import ConfluenceConnector
from backend.connectors.jira import JiraConnector
from backend.connectors.slack import SlackConnector
from backend.connectors.gdrive import GDriveConnector
from backend.retrieval.pipeline import RetrievalPipeline


def _decision(uid="alice", rid="r1", result=DecisionResult.ALLOW, reason="ok"):
    return Decision(
        user_id=uid, resource_id=rid, action=Action.READ,
        result=result, reason=reason, acl_version=1, policy_version=1,
        timestamp=datetime(2026, 9, 28, 12, tzinfo=timezone.utc),
    )


def _connectors():
    return [ConfluenceConnector(), JiraConnector(),
            SlackConnector(), GDriveConnector()]


# -- Chain construction & clean verification --------------------------

def test_empty_chain_head_is_genesis():
    chain = HashChain()
    assert chain.head_hash() == GENESIS_HASH
    assert chain.verify().valid is True


def test_first_event_links_to_genesis():
    chain = HashChain()
    ev = chain.append_decision(_decision(), "q1")
    assert ev.previous_hash == GENESIS_HASH
    assert ev.event_hash != ""


def test_events_are_linked_in_order():
    chain = HashChain()
    e1 = chain.append_decision(_decision(rid="r1"), "q1")
    e2 = chain.append_decision(_decision(rid="r2"), "q1")
    assert e2.previous_hash == e1.event_hash


def test_clean_chain_verifies():
    chain = HashChain()
    for i in range(5):
        chain.append_decision(_decision(rid=f"r{i}"), "q1")
    assert chain.verify().valid is True
    assert len(chain) == 5


# -- Tamper detection --------------------------------------------------

def test_tamper_field_detected():
    chain = HashChain()
    chain.append_decision(_decision(rid="r1"), "q1")
    chain.append_decision(_decision(rid="r2"), "q1")
    # Mutate a stored event's reason without recomputing its hash.
    chain.events()[0].reason = "TAMPERED"
    result = chain.verify()
    assert result.valid is False
    assert result.broken_at_index == 0
    assert "tampered" in result.reason


def test_tamper_decision_flip_detected():
    chain = HashChain()
    chain.append_decision(_decision(result=DecisionResult.DENY), "q1")
    chain.append_decision(_decision(rid="r2"), "q1")
    # Attacker flips a deny into an allow after the fact.
    chain.events()[0].decision = "allow"
    assert chain.verify().valid is False


def test_broken_link_detected():
    chain = HashChain()
    chain.append_decision(_decision(rid="r1"), "q1")
    chain.append_decision(_decision(rid="r2"), "q1")
    # Sever the link between event 1 and event 0.
    chain.events()[1].previous_hash = "deadbeef" * 8
    result = chain.verify()
    assert result.valid is False
    assert result.broken_at_index == 1
    assert "broken_link" in result.reason


def test_reordering_detected():
    chain = HashChain()
    chain.append_decision(_decision(rid="r1"), "q1")
    chain.append_decision(_decision(rid="r2"), "q1")
    chain.append_decision(_decision(rid="r3"), "q1")
    evs = chain._events
    evs[1], evs[2] = evs[2], evs[1]  # swap two events
    assert chain.verify().valid is False


def test_deletion_detected():
    chain = HashChain()
    chain.append_decision(_decision(rid="r1"), "q1")
    chain.append_decision(_decision(rid="r2"), "q1")
    chain.append_decision(_decision(rid="r3"), "q1")
    del chain._events[1]  # drop the middle event
    assert chain.verify().valid is False


# -- Canonical serialization ------------------------------------------

def test_canonical_payload_is_deterministic():
    d = _decision()
    a = event_from_decision(d, "q1", "e1")
    b = event_from_decision(d, "q1", "e1")
    assert a.canonical_payload() == b.canonical_payload()


def test_hash_depends_on_previous_hash():
    ev = AuditEvent(
        event_id="e1", user_id="alice", query_id="q1", resource_id="r1",
        action="read", decision="allow", reason="ok",
        acl_version=1, policy_version=1,
        timestamp=datetime(2026, 9, 28, tzinfo=timezone.utc),
    )
    h1 = compute_hash(GENESIS_HASH, ev)
    h2 = compute_hash("f" * 64, ev)
    assert h1 != h2


# -- INV4: every decision audited -------------------------------------

def test_every_pipeline_decision_is_audited():
    pipe = RetrievalPipeline(_connectors())
    alice = IdentityStore().get_user("alice")
    result = pipe.run(alice, "database migration payment security", k=20)
    chain = HashChain()
    chain.append_decisions(result.outcome.decisions, "q-alice-1")
    # One event per decision, chain verifies, order preserved.
    assert len(chain) == len(result.outcome.decisions)
    assert chain.verify().valid is True


def test_denies_are_audited_too():
    pipe = RetrievalPipeline(_connectors())
    bob = IdentityStore().get_user("bob")  # contractor, will be denied a lot
    result = pipe.run(bob, "security breach incident credential", k=20)
    chain = HashChain()
    chain.append_decisions(result.outcome.decisions, "q-bob-1")
    engine = AuditQueryEngine(chain)
    denies = engine.run(AuditQuery(decision="deny"))
    assert denies.count >= 1
    assert denies.verification.valid is True


# -- Audit query API (Demo 4) -----------------------------------------

def test_query_by_user():
    chain = HashChain()
    chain.append_decision(_decision(uid="alice", rid="r1"), "q1")
    chain.append_decision(_decision(uid="bob", rid="r2"), "q2")
    chain.append_decision(_decision(uid="alice", rid="r3"), "q3")
    engine = AuditQueryEngine(chain)
    res = engine.for_user("alice")
    assert res.count == 2
    assert all(e.user_id == "alice" for e in res.events)


def test_query_by_resource_substring():
    chain = HashChain()
    chain.append_decision(_decision(rid="jira:payment-gateway-1"), "q1")
    chain.append_decision(_decision(rid="confluence:db-plan"), "q1")
    chain.append_decision(_decision(rid="slack:payment-gateway-thread"), "q1")
    engine = AuditQueryEngine(chain)
    res = engine.for_resource_substring("payment-gateway")
    assert res.count == 2


def test_query_by_decision_counts():
    chain = HashChain()
    chain.append_decision(_decision(result=DecisionResult.ALLOW, rid="r1"), "q1")
    chain.append_decision(_decision(result=DecisionResult.DENY, rid="r2"), "q1")
    chain.append_decision(_decision(result=DecisionResult.ALLOW, rid="r3"), "q1")
    engine = AuditQueryEngine(chain)
    res = engine.run(AuditQuery())
    assert res.allow_count == 2
    assert res.deny_count == 1


def test_query_by_time_window():
    chain = HashChain()
    base = datetime(2026, 9, 28, 12, tzinfo=timezone.utc)
    e1 = _decision(rid="r1"); e1.timestamp = base
    e2 = _decision(rid="r2"); e2.timestamp = base + timedelta(days=10)
    chain.append_decision(e1, "q1")
    chain.append_decision(e2, "q1")
    engine = AuditQueryEngine(chain)
    res = engine.run(AuditQuery(since=base + timedelta(days=5)))
    assert res.count == 1
    assert res.events[0].resource_id == "r2"


def test_query_reports_tamper_status():
    chain = HashChain()
    chain.append_decision(_decision(rid="r1"), "q1")
    chain.append_decision(_decision(rid="r2"), "q1")
    chain.events()[0].reason = "TAMPERED"
    engine = AuditQueryEngine(chain)
    res = engine.run(AuditQuery())
    assert res.verification.valid is False


# -- File-based persistence + tamper detection (realistic insider edit) --

def _decn(uid="alice", rid="r1", result=DecisionResult.ALLOW, reason="ok"):
    return Decision(
        user_id=uid, resource_id=rid, action=Action.READ,
        result=result, reason=reason, acl_version=1, policy_version=1,
        timestamp=datetime(2026, 9, 28, 12, tzinfo=timezone.utc),
    )


def test_persist_on_append_writes_file(tmp_path):
    log = str(tmp_path / "audit_log.jsonl")
    chain = HashChain(persist_path=log)
    chain.append_decision(_decn(rid="r1"), "q1")
    chain.append_decision(_decn(rid="r2"), "q1")
    assert os.path.exists(log)
    import json
    data = _read_log(log)
    assert len(data) == 2


def test_verify_file_clean(tmp_path):
    log = str(tmp_path / "audit_log.jsonl")
    chain = HashChain(persist_path=log)
    for i in range(3):
        chain.append_decision(_decn(rid=f"r{i}"), "q1")
    result = chain.verify_file()
    assert result.valid is True


def test_verify_file_detects_hand_edit(tmp_path):
    """Simulate an insider editing the log file to flip a DENY to ALLOW."""
    import json
    log = str(tmp_path / "audit_log.jsonl")
    chain = HashChain(persist_path=log)
    chain.append_decision(_decn(rid="r1", result=DecisionResult.DENY, reason="no_access"), "q1")
    chain.append_decision(_decn(rid="r2"), "q1")

    # Edit the file out-of-band: flip event 0's decision deny -> allow.
    data = _read_log(log)
    data[0]["decision"] = "allow"
    _write_log(log, data)

    # In-memory chain still "verifies" (it wasn't touched) — but the FILE does not.
    result = chain.verify_file()
    assert result.valid is False
    assert result.broken_at_index == 0
    assert "tampered" in result.reason


def test_verify_file_detects_corrupt_json(tmp_path):
    log = str(tmp_path / "audit_log.jsonl")
    chain = HashChain(persist_path=log)
    chain.append_decision(_decn(), "q1")
    open(log, "w", encoding="utf-8").write("{ this is not valid json ]")
    result = chain.verify_file()
    assert result.valid is False
    assert "corrupt_json" in result.reason


def test_verify_file_no_path():
    chain = HashChain()  # no persist_path
    result = chain.verify_file()
    assert result.valid is False
    assert "no_persist_path" in result.reason


# -- The question is part of the tamper-evident record ---------------------
#
# The challenge requires the trail to capture "who, what (query + retrieved
# doc IDs + final answer), when". Every event of a query carries the question.

def test_question_recorded_on_every_event_of_a_query():
    from backend.agents.orchestrator import Orchestrator
    orch = Orchestrator(_connectors())
    alice = IdentityStore().get_user("alice")
    q = "What is the status of the database migration?"
    resp = orch.handle(alice, q, k=20)
    events = [e for e in orch.audit.events() if e.query_id == resp.query_id]
    assert len(events) >= 2  # decisions + the answer event
    assert all(e.question == q for e in events)


def test_question_is_hashed_so_editing_it_is_detected(tmp_path):
    import json
    log = str(tmp_path / "audit_log.jsonl")
    chain = HashChain(persist_path=log)
    chain.append_decision(_decn(rid="r1"), "q1", question="db migration status?")
    data = _read_log(log)
    assert data[0]["question"] == "db migration status?"
    data[0]["question"] = "something innocuous"
    _write_log(log, data)
    assert chain.verify_file().valid is False


# -- The answer's citation map is part of the tamper-evident record --------
#
# The logged answer text carries [1], [2] markers; without the marker ->
# resource map a compliance officer cannot tell which document [2] was.

def test_answer_event_records_citation_map():
    from backend.agents.orchestrator import Orchestrator
    orch = Orchestrator(_connectors())
    alice = IdentityStore().get_user("alice")
    resp = orch.handle(alice, "What is the status of the database migration?", k=20)
    answer_event = [e for e in orch.audit.events()
                    if e.query_id == resp.query_id and e.resource_id is None][0]
    assert answer_event.citations == [
        {"marker": c.marker, "resource_id": c.resource_id} for c in resp.citations
    ]
    assert answer_event.citations  # the demo question is answered with citations


def test_citation_map_is_hashed_so_editing_it_is_detected(tmp_path):
    import json
    log = str(tmp_path / "audit_log.jsonl")
    chain = HashChain(persist_path=log)
    chain.append_decision(
        _decn(rid=None), "q1", detail="Phase 3 is next [1].",
        citations=[{"marker": "[1]", "resource_id": "MIG-231"}],
    )
    data = _read_log(log)
    assert data[0]["citations"] == [{"marker": "[1]", "resource_id": "MIG-231"}]
    data[0]["citations"][0]["resource_id"] = "confluence:q3-breach-report"
    _write_log(log, data)
    assert chain.verify_file().valid is False


# The log is append-only JSON Lines: one event per line.
def _read_log(path):
    import json
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _write_log(path, events):
    import json
    with open(path, "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")


# -- Append-only persistence: tampering is never "healed" -----------------

def test_tamper_survives_later_appends(tmp_path):
    """A hand-edit must stay detectable after new events are logged. (The old
    full-file rewrite on every append silently restored the original.)"""
    log = str(tmp_path / "audit_log.jsonl")
    chain = HashChain(persist_path=log)
    chain.append_decision(_decn(rid="r1", result=DecisionResult.DENY, reason="no"), "q1")
    data = _read_log(log)
    data[0]["decision"] = "allow"
    _write_log(log, data)
    chain.append_decision(_decn(rid="r2"), "q2")
    chain.append_decision(_decn(rid="r3"), "q3")
    result = chain.verify_file()
    assert result.valid is False
    assert result.broken_at_index == 0
    assert _read_log(log)[0]["decision"] == "allow"  # the edit is still there


def test_appends_never_rewrite_earlier_lines(tmp_path):
    log = tmp_path / "audit_log.jsonl"
    chain = HashChain(persist_path=str(log))
    chain.append_decision(_decn(rid="r1"), "q1")
    first = log.read_bytes()
    chain.append_decision(_decn(rid="r2"), "q2")
    assert log.read_bytes().startswith(first)
    assert len(_read_log(str(log))) == 2


def test_deleting_the_newest_events_is_detected(tmp_path):
    """Dropping lines from the end leaves a self-consistent prefix; it is
    caught by comparing the file with the chain the server holds."""
    log = str(tmp_path / "audit_log.jsonl")
    chain = HashChain(persist_path=log)
    for i in range(3):
        chain.append_decision(_decn(rid=f"r{i}"), "q")
    _write_log(log, _read_log(log)[:2])
    result = chain.verify_file()
    assert result.valid is False
    assert "truncated" in result.reason
