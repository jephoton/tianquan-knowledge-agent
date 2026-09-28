"""Tests for M9 — no-metadata-leak & negative cases (Demo 2).

Run with: python -m pytest tests/test_m9_no_metadata_leak.py -v

The property under test (INV7 NoMetadataLeakOnDeny) at the system level:
for a query where a resource is DENIED, the denial is recorded in the audit
trail, but the denied resource's title, id, and distinctive content never
leak into the user-facing answer or citations — and the message reveals
nothing about whether restricted content exists.

These are end-to-end tests through the orchestrator (retrieval -> audit ->
answer), complementing the unit-level INV7 tests in test_m6_answer_agent.py.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models import DecisionResult
from backend.agents.orchestrator import Orchestrator
from backend.agents.answer_agent import NO_ACCESS_MESSAGE
from backend.auth.identity import IdentityStore
from backend.connectors.confluence import ConfluenceConnector
from backend.connectors.jira import JiraConnector
from backend.connectors.slack import SlackConnector
from backend.connectors.gdrive import GDriveConnector


# Distinctive strings that must NEVER appear in a denied user's answer.
# Drawn from the confidential Q3 breach report seed data.
BREACH_TITLE = "Q3 Security Incident Report"
BREACH_CONTENT_MARKERS = [
    "unauthorized actor",
    "leaked service account",
    "2,000 staging customer records",
]
BREACH_RESOURCE_ID = "confluence:q3-breach-report"


def _orchestrator():
    return Orchestrator([
        ConfluenceConnector(), JiraConnector(),
        SlackConnector(), GDriveConnector(),
    ])


def _user(uid):
    return IdentityStore().get_user(uid)


# -- Contractor sees the canonical no-leak message --------------------

def test_contractor_denied_gets_canonical_message():
    o = _orchestrator()
    bob = _user("bob")
    resp = o.handle(bob, "Q3 security incident report data breach", k=20)
    assert resp.no_access is True
    assert resp.answer == NO_ACCESS_MESSAGE
    assert resp.citations == []


def test_no_leak_answer_omits_denied_title_and_content():
    o = _orchestrator()
    bob = _user("bob")
    resp = o.handle(bob, "Q3 security incident report data breach credential", k=20)
    answer_lower = resp.answer.lower()
    assert BREACH_TITLE.lower() not in answer_lower
    for marker in BREACH_CONTENT_MARKERS:
        assert marker.lower() not in answer_lower


def test_no_leak_citations_never_include_denied_resource():
    o = _orchestrator()
    bob = _user("bob")
    resp = o.handle(bob, "security breach incident report", k=20)
    cited_ids = [c.resource_id for c in resp.citations]
    assert BREACH_RESOURCE_ID not in cited_ids


# -- The denial is still auditable (nothing hidden from compliance) ---

def test_denied_resource_recorded_in_audit_not_in_answer():
    """The core Demo 2 property: denied to the user, visible to the auditor."""
    o = _orchestrator()
    bob = _user("bob")
    resp = o.handle(bob, "Q3 security incident report data breach", k=20)

    # (a) The denied resource must NOT be in the user-facing surface.
    assert BREACH_RESOURCE_ID not in [c.resource_id for c in resp.citations]
    assert BREACH_TITLE.lower() not in resp.answer.lower()

    # (b) But it MUST be recorded as a DENY in the audit trail.
    deny_ids = [
        e.resource_id for e in o.audit.events()
        if e.decision == DecisionResult.DENY.value
    ]
    assert BREACH_RESOURCE_ID in deny_ids
    assert o.audit.verify().valid is True


def test_denial_reason_recorded_but_not_leaked_to_user():
    o = _orchestrator()
    bob = _user("bob")
    resp = o.handle(bob, "Q3 security incident report", k=20)
    # A deny reason exists in the decisions (for the inspector / audit)...
    deny = next(
        (d for d in resp.decisions
         if d.resource_id == BREACH_RESOURCE_ID
         and d.result == DecisionResult.DENY),
        None,
    )
    assert deny is not None
    assert deny.reason  # non-empty, for auditors
    # ...but the user answer is the canonical message, not the reason.
    assert resp.answer == NO_ACCESS_MESSAGE
    assert deny.reason not in resp.answer


# -- Denial does not confirm existence (same message when nothing exists) --

def test_denial_message_identical_to_no_match():
    """A denied query and a genuinely-empty query yield the SAME message,
    so the user cannot distinguish "denied" from "does not exist"."""
    o = _orchestrator()
    bob = _user("bob")
    denied = o.handle(bob, "Q3 security incident breach report", k=20)
    no_match = o.handle(bob, "zxqw nonexistent gibberish topic 12345", k=20)
    assert denied.no_access is True
    assert no_match.no_access is True
    assert denied.answer == no_match.answer == NO_ACCESS_MESSAGE


# -- Authorized user is unaffected (control) --------------------------

def test_security_team_still_sees_breach_content():
    o = _orchestrator()
    charlie = _user("charlie")  # security_team
    resp = o.handle(charlie, "Q3 security incident report data breach", k=20)
    assert resp.no_access is False
    assert BREACH_RESOURCE_ID in [c.resource_id for c in resp.citations]
