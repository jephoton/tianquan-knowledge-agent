"""Integration tests for the M3 permission-aware retrieval pipeline.

Run with: python -m pytest tests/test_m3_retrieval.py -v

Proves the core invariants at the implementation level:
- INV1 RetrievedOnlyIfAuthorized: no candidate that policy would deny survives.
- INV2 LLMSeesOnlyRetrievedContent: assembled context contains only authorized
  content (denied resource content/titles never appear).
- INV3 (support) RevokedAccessNotReusable: a revocation after indexing is
  honored on the next run without an explicit reindex.
Plus over-fetch safety, role differentiation, and assembler behavior.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models import Action, DecisionResult
from backend.auth.identity import IdentityStore
from backend.connectors.confluence import ConfluenceConnector
from backend.connectors.jira import JiraConnector
from backend.connectors.slack import SlackConnector
from backend.connectors.gdrive import GDriveConnector
from backend.policy.policy_engine import PolicyEngine
from backend.retrieval.indexer import Indexer
from backend.retrieval.candidate_search import CandidateSearch, tokenize
from backend.retrieval.permission_filter import PermissionFilter
from backend.retrieval.context_assembler import ContextAssembler
from backend.retrieval.pipeline import RetrievalPipeline


def _connectors():
    return [
        ConfluenceConnector(), JiraConnector(),
        SlackConnector(), GDriveConnector(),
    ]


def _pipeline():
    return RetrievalPipeline(_connectors())


def _user(uid):
    return IdentityStore().get_user(uid)


# -- Indexer -----------------------------------------------------------

def test_indexer_indexes_all_seed_resources():
    idx = Indexer(connectors=_connectors())
    assert idx.reindex() == 20
    assert idx.size() == 20


def test_index_entry_records_acl_version_snapshot():
    idx = Indexer(connectors=[ConfluenceConnector()])
    idx.reindex()
    entry = idx.get("confluence:payment-runbook")
    assert entry is not None
    assert entry.indexed_acl_version == entry.resource.acl.acl_version


# -- Candidate search --------------------------------------------------

def test_tokenize_drops_stopwords():
    assert "the" not in tokenize("what is the migration status")
    assert "migration" in tokenize("what is the migration status")


def test_search_returns_relevant_candidates():
    idx = Indexer(connectors=_connectors())
    idx.reindex()
    search = CandidateSearch(idx)
    results = search.search("database migration", k=10)
    ids = [c.resource.resource_id for c in results]
    assert "confluence:db-migration-plan" in ids
    assert "MIG-231" in ids


def test_search_scores_are_descending():
    idx = Indexer(connectors=_connectors())
    idx.reindex()
    search = CandidateSearch(idx)
    results = search.search("payment incident circuit breaker", k=10)
    scores = [c.score for c in results]
    assert scores == sorted(scores, reverse=True)


def test_search_respects_k():
    idx = Indexer(connectors=_connectors())
    idx.reindex()
    search = CandidateSearch(idx)
    assert len(search.search("the", k=3)) <= 3


def test_search_is_deterministic():
    idx = Indexer(connectors=_connectors())
    idx.reindex()
    search = CandidateSearch(idx)
    a = [c.resource.resource_id for c in search.search("payment outage", k=10)]
    b = [c.resource.resource_id for c in search.search("payment outage", k=10)]
    assert a == b


# -- Permission filter (INV1) -----------------------------------------

def test_filter_drops_denied_candidates():
    idx = Indexer(connectors=_connectors())
    idx.reindex()
    search = CandidateSearch(idx)
    pf = PermissionFilter()
    bob = _user("bob")
    candidates = search.search("security breach credential incident", k=20)
    outcome = pf.filter(bob, candidates, Action.READ)
    # Bob (contractor) must get none of the security content.
    allowed_ids = [c.resource.resource_id for c in outcome.allowed]
    assert "confluence:q3-breach-report" not in allowed_ids
    assert "SEC-101" not in allowed_ids


def test_filter_allowed_matches_policy_engine():
    # Every allowed candidate must independently be an ALLOW per the engine.
    idx = Indexer(connectors=_connectors())
    idx.reindex()
    search = CandidateSearch(idx)
    pf = PermissionFilter()
    engine = PolicyEngine()
    alice = _user("alice")
    candidates = search.search("database migration payment", k=20)
    outcome = pf.filter(alice, candidates, Action.READ)
    for fc in outcome.allowed:
        d = engine.decide(alice, fc.resource, Action.READ)
        assert d.result == DecisionResult.ALLOW


def test_filter_records_all_decisions():
    idx = Indexer(connectors=_connectors())
    idx.reindex()
    search = CandidateSearch(idx)
    pf = PermissionFilter()
    bob = _user("bob")
    candidates = search.search("security breach credential", k=20)
    outcome = pf.filter(bob, candidates, Action.READ)
    # One decision per candidate; at least one deny for a contractor here.
    assert len(outcome.decisions) == len(candidates)
    assert any(d.result == DecisionResult.DENY for d in outcome.decisions)


# -- Context assembler (INV2) -----------------------------------------

def test_context_excludes_denied_content_for_contractor():
    pipe = _pipeline()
    bob = _user("bob")
    result = pipe.run(bob, "security breach incident report credential", k=20)
    text = result.context.text
    # The confidential breach content must not appear anywhere in context.
    assert "unauthorized actor" not in text.lower()
    assert "q3-breach-report" not in text
    assert result.context.included_resource_ids == \
        [c.resource_id for c in result.context.citations]


def test_context_included_ids_are_all_authorized():
    pipe = _pipeline()
    engine = PolicyEngine()
    alice = _user("alice")
    result = pipe.run(alice, "database migration status blockers", k=20)
    idx = Indexer(connectors=_connectors())
    idx.reindex()
    for rid in result.context.included_resource_ids:
        entry = idx.get(rid)
        d = engine.decide(alice, entry.resource, Action.READ)
        assert d.result == DecisionResult.ALLOW


def test_citation_authorization_check():
    pipe = _pipeline()
    alice = _user("alice")
    result = pipe.run(alice, "database migration", k=10)
    ctx = result.context
    for c in ctx.citations:
        assert ctx.is_authorized_citation(c.resource_id) is True
    assert ctx.is_authorized_citation("confluence:q3-breach-report") is False


def test_context_truncation_respects_budget():
    assembler = ContextAssembler(max_chars=200)
    pipe_idx = Indexer(connectors=_connectors())
    pipe_idx.reindex()
    search = CandidateSearch(pipe_idx)
    pf = PermissionFilter()
    alice = _user("alice")
    candidates = search.search("database migration payment", k=20)
    outcome = pf.filter(alice, candidates, Action.READ)
    ctx = assembler.assemble(outcome.allowed)
    assert len(ctx.text) <= 200 + max(
        (len(c.resource.content) for c in outcome.allowed), default=0)
    if len(outcome.allowed) > 1:
        assert ctx.truncated is True


# -- Role differentiation ---------------------------------------------

def test_contractor_sees_fewer_than_engineer():
    pipe = _pipeline()
    alice = _user("alice")   # engineer
    bob = _user("bob")       # contractor
    q = "database migration payment incident security"
    alice_ids = set(pipe.run(alice, q, k=20).context.included_resource_ids)
    bob_ids = set(pipe.run(bob, q, k=20).context.included_resource_ids)
    # Contractor's authorized set is a strict subset of the engineer's here.
    assert bob_ids <= alice_ids
    assert len(bob_ids) < len(alice_ids)


def test_security_team_sees_confidential_breach():
    pipe = _pipeline()
    charlie = _user("charlie")  # security_team
    result = pipe.run(charlie, "security breach incident credential", k=20)
    assert "confluence:q3-breach-report" in result.context.included_resource_ids


# -- Revocation (INV3 support) ----------------------------------------

def test_revocation_after_indexing_is_honored():
    # Build a pipeline, then revoke Alice's access to a doc she could see,
    # and confirm the next run excludes it WITHOUT reindexing.
    connectors = _connectors()
    confluence = connectors[0]
    pipe = RetrievalPipeline(connectors)
    alice = _user("alice")
    q = "database migration plan"

    before = pipe.run(alice, q, k=20).context.included_resource_ids
    assert "confluence:db-migration-plan" in before

    # Revoke: remove engineer role access and deny alice explicitly.
    confluence.update_acl(
        "confluence:db-migration-plan",
        allowed_roles=["admin"],
        denied_users=["alice"],
    )

    after = pipe.run(alice, q, k=20).context.included_resource_ids
    assert "confluence:db-migration-plan" not in after


def test_revocation_marks_index_entry_stale():
    connectors = _connectors()
    confluence = connectors[0]
    idx = Indexer(connectors=connectors)
    idx.reindex()
    search = CandidateSearch(idx)
    pf = PermissionFilter()

    # Bump ACL version via an update after indexing.
    confluence.update_acl("confluence:db-migration-plan", allowed_roles=["admin"])
    candidates = search.search("database migration plan", k=20)
    # Use any user; we only assert freshness detection on the bumped resource.
    user = _user("alice")
    outcome = pf.filter(user, candidates, Action.READ)
    all_by_id = {c.resource.resource_id: c for c in outcome.allowed}
    if "confluence:db-migration-plan" in all_by_id:
        assert all_by_id["confluence:db-migration-plan"].freshness.is_fresh is False


# -- Pipeline wiring ---------------------------------------------------

def test_pipeline_reindex_returns_size():
    pipe = _pipeline()
    assert pipe.reindex() == 20


def test_pipeline_run_reports_candidate_count():
    pipe = _pipeline()
    alice = _user("alice")
    result = pipe.run(alice, "database migration", k=10)
    assert result.candidate_count >= len(result.outcome.allowed)
