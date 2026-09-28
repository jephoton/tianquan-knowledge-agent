"""Tests for M7 live revocation handling (Demo 3).

Run with: python -m pytest tests/test_m7_revocation.py -v

Covers:
- PermissionAdmin revoke/grant for users and roles, with version transitions.
- Deny-list precedence on user revocation.
- End-to-end via the orchestrator: revoke -> next query excludes the resource
  without a reindex, and the audit trail records the DENY at the new ACL
  version (INV3 at the system level).
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from backend.models import Action, DecisionResult
from backend.policy.admin import PermissionAdmin, ResourceNotFound
from backend.agents.orchestrator import Orchestrator
from backend.auth.identity import IdentityStore
from backend.connectors.confluence import ConfluenceConnector
from backend.connectors.jira import JiraConnector
from backend.connectors.slack import SlackConnector
from backend.connectors.gdrive import GDriveConnector


def _connectors():
    return [ConfluenceConnector(), JiraConnector(),
            SlackConnector(), GDriveConnector()]


def _user(uid):
    return IdentityStore().get_user(uid)


# -- PermissionAdmin unit behavior ------------------------------------

def test_revoke_role_bumps_version():
    connectors = _connectors()
    admin = PermissionAdmin(connectors)
    change = admin.revoke_role("confluence:db-migration-plan", "engineer")
    assert change.change == "revoke"
    assert change.subject == "engineer"
    assert change.new_version == change.previous_version + 1
    assert change.version_transition == \
        f"v{change.previous_version} -> v{change.new_version}"


def test_revoke_user_adds_to_deny_list():
    connectors = _connectors()
    confluence = connectors[0]
    admin = PermissionAdmin(connectors)
    admin.revoke_user("confluence:db-migration-plan", "alice")
    acl = confluence.get_acl("confluence:db-migration-plan")
    assert "alice" in acl.denied_users
    assert "alice" not in acl.allowed_users


def test_grant_user_clears_deny():
    connectors = _connectors()
    admin = PermissionAdmin(connectors)
    admin.revoke_user("confluence:db-migration-plan", "alice")
    change = admin.grant_user("confluence:db-migration-plan", "alice")
    acl = connectors[0].get_acl("confluence:db-migration-plan")
    assert "alice" not in acl.denied_users
    assert "alice" in acl.allowed_users
    assert change.change == "grant"


def test_grant_role_adds_role():
    connectors = _connectors()
    admin = PermissionAdmin(connectors)
    change = admin.grant_role("confluence:auth-service-design", "contractor")
    acl = connectors[0].get_acl("confluence:auth-service-design")
    assert "contractor" in acl.allowed_roles
    assert change.new_version == change.previous_version + 1


def test_revoke_unknown_resource_raises():
    admin = PermissionAdmin(_connectors())
    with pytest.raises(ResourceNotFound):
        admin.revoke_user("nonexistent:resource", "alice")


def test_admin_resolves_correct_connector_across_sources():
    admin = PermissionAdmin(_connectors())
    # A Jira-owned resource should be found and versioned by the Jira connector.
    change = admin.revoke_role("MIG-231", "engineer")
    assert change.resource_id == "MIG-231"
    assert change.new_version == change.previous_version + 1


# -- End-to-end via orchestrator (Demo 3) -----------------------------

def test_revocation_excludes_resource_next_query_no_reindex():
    o = Orchestrator(_connectors())
    alice = _user("alice")
    q = "database migration plan"

    before = o.handle(alice, q, k=20)
    before_ids = [c.resource_id for c in before.citations]
    assert "confluence:db-migration-plan" in before_ids

    o.admin.revoke_role("confluence:db-migration-plan", "engineer")

    after = o.handle(alice, q, k=20)
    after_ids = [c.resource_id for c in after.citations]
    assert "confluence:db-migration-plan" not in after_ids


def test_revocation_recorded_as_deny_at_new_version():
    o = Orchestrator(_connectors())
    alice = _user("alice")
    q = "database migration plan"

    o.handle(alice, q, k=20)
    change = o.admin.revoke_role("confluence:db-migration-plan", "engineer")
    o.handle(alice, q, k=20)

    # Find the audit event for the revoked resource at the new ACL version.
    deny_events = [
        e for e in o.audit.events()
        if e.resource_id == "confluence:db-migration-plan"
        and e.decision == DecisionResult.DENY.value
    ]
    assert any(e.acl_version == change.new_version for e in deny_events)
    assert o.audit.verify().valid is True


def test_grant_restores_access_next_query():
    o = Orchestrator(_connectors())
    alice = _user("alice")
    q = "database migration plan"

    o.admin.revoke_user("confluence:db-migration-plan", "alice")
    denied = o.handle(alice, q, k=20)
    assert "confluence:db-migration-plan" not in \
        [c.resource_id for c in denied.citations]

    o.admin.grant_user("confluence:db-migration-plan", "alice")
    restored = o.handle(alice, q, k=20)
    assert "confluence:db-migration-plan" in \
        [c.resource_id for c in restored.citations]


def test_audit_chain_intact_across_revocation():
    o = Orchestrator(_connectors())
    alice = _user("alice")
    o.handle(alice, "database migration", k=20)
    o.admin.revoke_role("confluence:db-migration-plan", "engineer")
    o.handle(alice, "database migration", k=20)
    assert o.audit.verify().valid is True
