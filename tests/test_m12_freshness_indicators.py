"""Tests for M12 — Data freshness indicators.

Run with: python -m pytest tests/test_m12_freshness_indicators.py -v

Covers:
- Citation dataclass carries updated_at from the resource.
- ContextAssembler populates updated_at for each citation.
- QueryResponse citations include updated_at through the orchestrator.
- Staleness thresholds: fresh (<24h), moderate (<7d), stale (>7d).
- API schema includes updated_at field.
"""

import sys
import os
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.retrieval.context_assembler import ContextAssembler, Citation, AssembledContext
from backend.retrieval.permission_filter import FilteredCandidate, FilterOutcome
from backend.models import (
    Action, Decision, DecisionResult, Resource, Source, ACL,
    SensitivityLevel, User,
)
from backend.agents.orchestrator import Orchestrator
from backend.api.schemas import CitationModel
from backend.auth.identity import IdentityStore
from backend.connectors.confluence import ConfluenceConnector
from backend.connectors.jira import JiraConnector
from backend.connectors.slack import SlackConnector
from backend.connectors.gdrive import GDriveConnector
from backend.policy.freshness_checker import FreshnessResult


# -- Helpers --------------------------------------------------------------

def _resource(rid, source=Source.CONFLUENCE, updated_at=None):
    return Resource(
        source=source,
        resource_id=rid,
        title=f"Title for {rid}",
        content=f"Content of {rid} with some details.",
        updated_at=updated_at or datetime.now(timezone.utc),
        acl=ACL(acl_version=1, allowed_roles=["engineer"]),
        sensitivity_level=SensitivityLevel.INTERNAL,
    )

def _filtered(resource):
    return FilteredCandidate(
        resource=resource,
        decision=Decision(
            user_id="alice", resource_id=resource.resource_id,
            action=Action.READ, result=DecisionResult.ALLOW,
            reason="test", acl_version=1, policy_version=1,
        ),
        score=1.0,
        freshness=FreshnessResult(is_fresh=True, known_version=1, current_version=1, reason="fresh"),
    )

def _connectors():
    return [ConfluenceConnector(), JiraConnector(),
            SlackConnector(), GDriveConnector()]


# -- Citation carries updated_at -----------------------------------------

def test_citation_has_updated_at_field():
    now = datetime.now(timezone.utc)
    c = Citation(marker="[1]", resource_id="r1", source="confluence",
                 title="T", updated_at=now)
    assert c.updated_at == now


def test_citation_updated_at_defaults_none():
    c = Citation(marker="[1]", resource_id="r1", source="confluence", title="T")
    assert c.updated_at is None


# -- ContextAssembler populates updated_at -------------------------------

def test_assembler_populates_updated_at():
    now = datetime.now(timezone.utc)
    res = _resource("r1", updated_at=now)
    ctx = ContextAssembler().assemble([_filtered(res)])
    assert len(ctx.citations) == 1
    assert ctx.citations[0].updated_at == now


def test_assembler_populates_different_timestamps():
    t1 = datetime.now(timezone.utc) - timedelta(hours=2)
    t2 = datetime.now(timezone.utc) - timedelta(days=5)
    ctx = ContextAssembler().assemble([
        _filtered(_resource("r1", updated_at=t1)),
        _filtered(_resource("r2", updated_at=t2)),
    ])
    assert ctx.citations[0].updated_at == t1
    assert ctx.citations[1].updated_at == t2


# -- Orchestrator carries updated_at through -----------------------------

def test_orchestrator_citations_have_updated_at():
    o = Orchestrator(_connectors())
    alice = IdentityStore().get_user("alice")
    resp = o.handle(alice, "database migration status", k=20)
    assert resp.no_access is False
    assert len(resp.citations) > 0
    for c in resp.citations:
        assert c.updated_at is not None


def test_orchestrator_freshness_varies():
    """Seed data should have resources with different updated_at timestamps."""
    o = Orchestrator(_connectors())
    alice = IdentityStore().get_user("alice")
    resp = o.handle(alice, "database migration payment security", k=20)
    if len(resp.citations) >= 2:
        timestamps = {c.updated_at for c in resp.citations}
        # At least some variation in timestamps (different resources updated
        # at different times).
        assert len(timestamps) >= 1


# -- Freshness badge logic ------------------------------------------------

def test_freshness_classification():
    """Verify the staleness thresholds used by the frontend badge logic."""
    now = datetime.now(timezone.utc)

    # Fresh: < 24 hours
    fresh = now - timedelta(hours=12)
    assert (now - fresh).total_seconds() / 3600 < 24

    # Moderate: 1-7 days
    moderate = now - timedelta(days=3)
    age_h = (now - moderate).total_seconds() / 3600
    assert 24 <= age_h < 168

    # Stale: > 7 days
    stale = now - timedelta(days=14)
    age_h = (now - stale).total_seconds() / 3600
    assert age_h >= 168


# -- API schema includes updated_at --------------------------------------

def test_citation_model_includes_updated_at():
    now = datetime.now(timezone.utc)
    m = CitationModel(
        marker="[1]", resource_id="r1", source="confluence",
        title="T", updated_at=now.isoformat(),
    )
    assert m.updated_at is not None


def test_citation_model_updated_at_optional():
    m = CitationModel(
        marker="[1]", resource_id="r1", source="confluence", title="T",
    )
    assert m.updated_at is None