"""Tests for the M2 policy engine, permission mapping, and freshness checker.

Run with: python -m pytest tests/test_m2_policy_engine.py -v

Covers:
- Positive and negative authorization decisions.
- The fail-closed decision-gate ordering (deny-list, source, sensitivity, action).
- Source-specific permission rules (Confluence, Jira, Slack, GDrive).
- Sensitivity clearance by role.
- Action permission by role.
- ACL freshness checking (supports INV3: RevokedAccessNotReusable).
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone

from backend.models import (
    Source, SensitivityLevel, Action, DecisionResult,
    User, ACL, Resource,
)
from backend.policy.policy_engine import PolicyEngine, POLICY_VERSION
from backend.policy.permission_mapping import (
    check_action_permission,
    check_sensitivity_clearance,
    check_source_specific,
)
from backend.policy.freshness_checker import check_freshness, assert_fresh


def _now():
    return datetime.now(timezone.utc)


def _resource(source, acl, sensitivity=SensitivityLevel.INTERNAL, rid="r1"):
    return Resource(
        source=source, resource_id=rid, title="T",
        content="c", updated_at=_now(), acl=acl,
        sensitivity_level=sensitivity,
    )


# -- Decision-gate ordering & basics ----------------------------------

def test_allow_when_all_gates_pass():
    engine = PolicyEngine()
    res = _resource(
        Source.CONFLUENCE,
        ACL(1, allowed_roles=["engineer"], source_permissions={"space": "ENG"}),
    )
    alice = User("alice", "Alice", "a@e.com", roles=["engineer"])
    d = engine.decide(alice, res, Action.READ)
    assert d.result == DecisionResult.ALLOW
    assert d.acl_version == 1
    assert d.policy_version == POLICY_VERSION


def test_explicit_deny_list_overrides_role_grant():
    engine = PolicyEngine()
    res = _resource(
        Source.CONFLUENCE,
        ACL(5, allowed_roles=["engineer"], denied_users=["alice"],
            source_permissions={"space": "ENG"}),
    )
    alice = User("alice", "Alice", "a@e.com", roles=["engineer"])
    d = engine.decide(alice, res, Action.READ)
    assert d.result == DecisionResult.DENY
    assert d.reason == "explicit_deny_list"
    assert d.acl_version == 5


def test_deny_records_acl_version():
    engine = PolicyEngine()
    res = _resource(
        Source.CONFLUENCE,
        ACL(9, allowed_roles=["security_team"],
            source_permissions={"space": "SEC"}),
        sensitivity=SensitivityLevel.CONFIDENTIAL,
    )
    bob = User("bob", "Bob", "b@e.com", roles=["contractor"])
    d = engine.decide(bob, res, Action.READ)
    assert d.result == DecisionResult.DENY
    assert d.acl_version == 9


def test_decide_never_raises_returns_deny():
    engine = PolicyEngine()
    res = _resource(
        Source.SLACK,
        ACL(1, source_permissions={"channel": "x", "channel_type": "private"}),
    )
    stranger = User("stranger", "S", "s@e.com", roles=["contractor"])
    d = engine.decide(stranger, res, Action.READ)
    assert d.result == DecisionResult.DENY


# -- Source-specific: Confluence --------------------------------------

def test_confluence_named_page_blocks_space_role():
    # A 'named' page grants access only to explicitly named users/roles in the
    # ACL. A user whose access is merely space-level (role not in the page ACL)
    # is blocked. Here the ACL names only 'editors', so an engineer is blocked.
    res = _resource(
        Source.CONFLUENCE,
        ACL(1, allowed_roles=["editors"],
            source_permissions={"space": "ENG", "page_restriction": "named"}),
    )
    alice = User("alice", "Alice", "a@e.com", roles=["engineer"])
    ok, reason = check_source_specific(alice, res)
    assert ok is False
    assert "named_page_no_access" in reason


def test_confluence_named_page_allows_explicit_user():
    res = _resource(
        Source.CONFLUENCE,
        ACL(1, allowed_users=["alice"],
            source_permissions={"space": "ENG", "page_restriction": "named"}),
    )
    alice = User("alice", "Alice", "a@e.com", roles=["engineer"])
    ok, _ = check_source_specific(alice, res)
    assert ok is True


# -- Source-specific: Jira --------------------------------------------

def test_jira_security_issue_requires_security_role():
    res = _resource(
        Source.JIRA,
        ACL(1, allowed_roles=["engineer"],
            source_permissions={"project": "SEC", "issue_security": "security"}),
    )
    alice = User("alice", "Alice", "a@e.com", roles=["engineer"])
    charlie = User("charlie", "Charlie", "c@e.com", roles=["security_team"])
    assert check_source_specific(alice, res)[0] is False
    assert check_source_specific(charlie, res)[0] is True


# -- Source-specific: Slack -------------------------------------------

def test_slack_public_channel_open_to_all():
    res = _resource(
        Source.SLACK,
        ACL(1, source_permissions={"channel": "general", "channel_type": "public"}),
    )
    bob = User("bob", "Bob", "b@e.com", roles=["contractor"])
    assert check_source_specific(bob, res)[0] is True


def test_slack_private_channel_requires_membership():
    res = _resource(
        Source.SLACK,
        ACL(1, allowed_users=["alice"],
            source_permissions={"channel": "leadership", "channel_type": "private"}),
    )
    alice = User("alice", "Alice", "a@e.com", roles=["engineer"])
    bob = User("bob", "Bob", "b@e.com", roles=["contractor"])
    assert check_source_specific(alice, res)[0] is True
    assert check_source_specific(bob, res)[0] is False


# -- Source-specific: GDrive ------------------------------------------

def test_gdrive_explicit_user_share():
    res = _resource(
        Source.GDRIVE,
        ACL(1, allowed_users=["alice"], source_permissions={"drive": "eng"}),
    )
    alice = User("alice", "Alice", "a@e.com", roles=["engineer"])
    bob = User("bob", "Bob", "b@e.com", roles=["contractor"])
    assert check_source_specific(alice, res)[0] is True
    assert check_source_specific(bob, res)[0] is False


# -- Sensitivity clearance --------------------------------------------

def test_sensitivity_confidential_blocks_engineer():
    res = _resource(Source.GDRIVE, ACL(1), sensitivity=SensitivityLevel.CONFIDENTIAL)
    engineer = User("e", "E", "e@e.com", roles=["engineer"])
    ok, reason = check_sensitivity_clearance(engineer, res)
    assert ok is False
    assert "confidential_not_cleared" in reason


def test_sensitivity_confidential_allows_security():
    res = _resource(Source.GDRIVE, ACL(1), sensitivity=SensitivityLevel.CONFIDENTIAL)
    sec = User("c", "C", "c@e.com", roles=["security_team"])
    assert check_sensitivity_clearance(sec, res)[0] is True


def test_sensitivity_public_open_to_contractor():
    res = _resource(Source.GDRIVE, ACL(1), sensitivity=SensitivityLevel.PUBLIC)
    bob = User("bob", "Bob", "b@e.com", roles=["contractor"])
    assert check_sensitivity_clearance(bob, res)[0] is True


# -- Action permission -------------------------------------------------

def test_action_export_denied_for_engineer():
    engineer = User("e", "E", "e@e.com", roles=["engineer"])
    ok, reason = check_action_permission(engineer, Action.EXPORT)
    assert ok is False
    assert "not_permitted" in reason


def test_action_export_allowed_for_senior_engineer():
    senior = User("s", "S", "s@e.com", roles=["senior_engineer"])
    assert check_action_permission(senior, Action.EXPORT)[0] is True


def test_action_read_allowed_for_contractor():
    bob = User("bob", "Bob", "b@e.com", roles=["contractor"])
    assert check_action_permission(bob, Action.READ)[0] is True


# -- decide_many / filter_allowed -------------------------------------

def test_filter_allowed_excludes_denied():
    engine = PolicyEngine()
    allowed = _resource(
        Source.SLACK,
        ACL(1, source_permissions={"channel": "gen", "channel_type": "public"}),
        sensitivity=SensitivityLevel.PUBLIC,
        rid="ok",
    )
    denied = _resource(
        Source.SLACK,
        ACL(1, allowed_users=["someone"],
            source_permissions={"channel": "priv", "channel_type": "private"}),
        sensitivity=SensitivityLevel.PUBLIC,
        rid="no",
    )
    bob = User("bob", "Bob", "b@e.com", roles=["contractor"])
    results = engine.filter_allowed(bob, [allowed, denied], Action.READ)
    assert len(results) == 1
    assert results[0][0].resource_id == "ok"


def test_decide_many_returns_one_decision_per_resource():
    engine = PolicyEngine()
    resources = [
        _resource(Source.SLACK,
                  ACL(1, source_permissions={"channel": "g", "channel_type": "public"}),
                  rid=f"r{i}")
        for i in range(3)
    ]
    bob = User("bob", "Bob", "b@e.com", roles=["contractor"])
    decisions = engine.decide_many(bob, resources, Action.READ)
    assert len(decisions) == 3


# -- Freshness checker (INV3 support) ---------------------------------

def test_freshness_current_version():
    res = _resource(Source.SLACK, ACL(7))
    result = check_freshness(res, 7)
    assert result.is_fresh is True
    assert result.reason == "acl_version_current"


def test_freshness_stale_after_revocation():
    res = _resource(Source.SLACK, ACL(8))
    result = check_freshness(res, 7)
    assert result.is_fresh is False
    assert "stale" in result.reason


def test_freshness_anomaly_fails_closed():
    res = _resource(Source.SLACK, ACL(5))
    result = check_freshness(res, 9)
    assert result.is_fresh is False
    assert "anomaly" in result.reason


def test_assert_fresh_boolean():
    res = _resource(Source.SLACK, ACL(3))
    assert assert_fresh(res, 3) is True
    assert assert_fresh(res, 2) is False
