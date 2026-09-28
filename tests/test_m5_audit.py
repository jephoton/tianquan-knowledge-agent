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
