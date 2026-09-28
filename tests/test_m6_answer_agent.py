"""Tests for the M6 answer agent and orchestrator.

Run with: python -m pytest tests/test_m6_answer_agent.py -v

Covers:
- Answer grounding on authorized context.
- INV6 NoUnauthorizedCitation: citations not backed by context are stripped.
- INV7 NoMetadataLeakOnDeny: empty context -> canonical no-leak message.
- Orchestrator end-to-end: query -> retrieval -> audit -> answer -> audit,
  with a verifiable audit chain (INV4) and correct answers per persona.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models import Action, DecisionResult
from backend.agents.llm_client import StubLLMClient, LLMClient
from backend.agents.answer_agent import AnswerAgent, NO_ACCESS_MESSAGE
from backend.agents.orchestrator import Orchestrator
from backend.retrieval.context_assembler import (
    AssembledContext, Citation,
)
from backend.auth.identity import IdentityStore
from backend.connectors.confluence import ConfluenceConnector
from backend.connectors.jira import JiraConnector
from backend.connectors.slack import SlackConnector
from backend.connectors.gdrive import GDriveConnector


def _connectors():
    return [ConfluenceConnector(), JiraConnector(),
            SlackConnector(), GDriveConnector()]


def _ctx(*resource_ids):
    """Build an AssembledContext with numbered citations for given ids."""
    citations = [
        Citation(marker=f"[{i + 1}]", resource_id=rid,
                 source="confluence", title=f"T{i}")
        for i, rid in enumerate(resource_ids)
    ]
    text = "\n".join(f"{c.marker} {c.resource_id}\nbody" for c in citations)
    return AssembledContext(
        text=text,
        citations=citations,
        included_resource_ids=list(resource_ids),
    )


class _FixedLLM:
    """LLM stub returning a fixed string, for citation-validation tests."""

    def __init__(self, output: str):
        self._output = output

    def generate(self, prompt: str) -> str:
        return self._output


# -- LLM client / stub -------------------------------------------------

def test_stub_is_llm_client():
    assert isinstance(StubLLMClient(), LLMClient)


def test_stub_is_deterministic():
    stub = StubLLMClient()
    prompt = "ctx [1] and [2]"
    assert stub.generate(prompt) == stub.generate(prompt)


# -- Answer grounding --------------------------------------------------

def test_answer_grounds_on_context():
    agent = AnswerAgent(StubLLMClient())
    ctx = _ctx("r1", "r2")
    ans = agent.answer("what happened?", ctx)
    assert ans.grounded is True
    assert ans.no_access is False
    assert len(ans.citations) == 2


# -- INV7: no metadata leak on empty context --------------------------

def test_empty_context_returns_no_leak_message():
    agent = AnswerAgent(StubLLMClient())
    empty = AssembledContext(text="", citations=[], included_resource_ids=[])
    ans = agent.answer("show me the secret report", empty)
    assert ans.no_access is True
    assert ans.text == NO_ACCESS_MESSAGE
    assert ans.citations == []


def test_no_leak_message_reveals_nothing():
    agent = AnswerAgent(StubLLMClient())
    empty = AssembledContext(text="", citations=[], included_resource_ids=[])
    ans = agent.answer("q3 breach report", empty)
    # Must not echo the query subject or any resource identifier.
    assert "breach" not in ans.text.lower()
    assert "q3" not in ans.text.lower()


# -- INV6: unauthorized citations are stripped ------------------------

def test_unauthorized_citation_stripped():
    # LLM emits [1] (valid) and [9] (not in context) -> [9] removed.
    ctx = _ctx("r1")
    agent = AnswerAgent(_FixedLLM("See [1] and also [9] for details."))
    ans = agent.answer("q", ctx)
    assert "[9]" not in ans.text
    assert "[1]" in ans.text
    assert [c.marker for c in ans.citations] == ["[1]"]


def test_only_valid_citations_returned():
    ctx = _ctx("r1", "r2", "r3")
    agent = AnswerAgent(_FixedLLM("Per [2] and [3], and bogus [7]."))
    ans = agent.answer("q", ctx)
    markers = [c.marker for c in ans.citations]
    assert markers == ["[2]", "[3]"]
    assert "[7]" not in ans.text


def test_citations_map_to_authorized_resources():
    ctx = _ctx("confluence:db-migration-plan", "MIG-231")
    agent = AnswerAgent(_FixedLLM("Summary [1] [2]."))
    ans = agent.answer("q", ctx)
    cited_ids = {c.resource_id for c in ans.citations}
    assert cited_ids <= set(ctx.included_resource_ids)


# -- Orchestrator end-to-end ------------------------------------------

def test_orchestrator_allowed_query_grounded_answer():
    o = Orchestrator(_connectors())
    alice = IdentityStore().get_user("alice")
    resp = o.handle(alice, "database migration status blockers", k=20)
    assert resp.no_access is False
    assert len(resp.citations) >= 1
    assert resp.allow_count >= 1


def test_orchestrator_denied_query_no_leak():
    o = Orchestrator(_connectors())
    bob = IdentityStore().get_user("bob")  # contractor
    resp = o.handle(bob, "security breach incident report credential", k=20)
    assert resp.no_access is True
    assert resp.answer == NO_ACCESS_MESSAGE
    assert resp.citations == []


def test_orchestrator_audits_every_decision_and_answer():
    o = Orchestrator(_connectors())
    alice = IdentityStore().get_user("alice")
    resp = o.handle(alice, "database migration payment", k=20)
    # audit chain should contain one event per decision + one answer event.
    assert len(o.audit) == len(resp.decisions) + 1
    assert o.audit.verify().valid is True


def test_orchestrator_audit_chain_head_returned():
    o = Orchestrator(_connectors())
    alice = IdentityStore().get_user("alice")
    resp = o.handle(alice, "database migration", k=10)
    assert resp.audit_chain_head == o.audit.head_hash()
    assert resp.audit_chain_head != ""


def test_orchestrator_shared_chain_across_queries():
    o = Orchestrator(_connectors())
    alice = IdentityStore().get_user("alice")
    bob = IdentityStore().get_user("bob")
    o.handle(alice, "database migration", k=10)
    len_after_first = len(o.audit)
    o.handle(bob, "security breach", k=10)
    assert len(o.audit) > len_after_first
    assert o.audit.verify().valid is True


def test_orchestrator_answer_event_recorded_for_no_access():
    o = Orchestrator(_connectors())
    bob = IdentityStore().get_user("bob")
    o.handle(bob, "confidential security breach", k=20)
    # The final event is the answer event; for a no-access response it is a deny.
    last = o.audit.events()[-1]
    assert last.resource_id is None
    assert last.decision == DecisionResult.DENY.value
    assert last.reason == "answer_no_access"


def test_orchestrator_different_users_different_answers():
    o = Orchestrator(_connectors())
    alice = IdentityStore().get_user("alice")
    bob = IdentityStore().get_user("bob")
    q = "security breach incident report"
    charlie = IdentityStore().get_user("charlie")
    a = o.handle(alice, q, k=20)
    b = o.handle(bob, q, k=20)
    c = o.handle(charlie, q, k=20)
    # Contractor sees nothing; security team sees content; answers differ.
    assert b.no_access is True
    assert c.no_access is False
    assert c.answer != b.answer
