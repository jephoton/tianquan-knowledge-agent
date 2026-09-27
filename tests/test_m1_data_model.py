"""Tests for the data model, seed users, and mock connectors.

Run with: python -m pytest tests/test_m1_data_model.py -v
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone
from backend.models import (
    Source, SensitivityLevel, Action, DecisionResult,
    User, ACL, Resource, Decision,
)
from backend.auth.identity import IdentityStore, seed_users
from backend.auth.roles import ROLES, role_exists, get_role_permissions
from backend.connectors.confluence import ConfluenceConnector
from backend.connectors.jira import JiraConnector
from backend.connectors.slack import SlackConnector
from backend.connectors.gdrive import GDriveConnector


def _now():
    return datetime.now(timezone.utc)


# -- Model tests -------------------------------------------------------

def test_resource_authorized_by_role():
    res = Resource(
        source=Source.CONFLUENCE, resource_id="t1", title="T",
        content="c", updated_at=_now(),
        acl=ACL(1, allowed_roles=["engineer"]),
    )
    user = User("u1", "U", "u@e.com", roles=["engineer"])
    assert res.is_authorized(user) is True


def test_resource_denied_by_explicit_deny():
    res = Resource(
        source=Source.CONFLUENCE, resource_id="t2", title="T",
        content="c", updated_at=_now(),
        acl=ACL(1, allowed_roles=["engineer"], denied_users=["u1"]),
    )
    user = User("u1", "U", "u@e.com", roles=["engineer"])
    assert res.is_authorized(user) is False


def test_resource_authorized_by_explicit_allow():
    res = Resource(
        source=Source.CONFLUENCE, resource_id="t3", title="T",
        content="c", updated_at=_now(),
        acl=ACL(1, allowed_users=["bob"]),
    )
    user = User("bob", "Bob", "b@e.com", roles=["contractor"])
    assert res.is_authorized(user) is True


def test_resource_unauthorized_no_match():
    res = Resource(
        source=Source.CONFLUENCE, resource_id="t4", title="T",
        content="c", updated_at=_now(),
        acl=ACL(1, allowed_roles=["security_team"]),
    )
    user = User("bob", "Bob", "b@e.com", roles=["contractor"])
    assert res.is_authorized(user) is False


# -- User/Role tests ---------------------------------------------------

def test_seed_users_count():
    assert len(seed_users()) == 7


def test_alice_is_engineer():
    alice = seed_users()["alice"]
    assert "engineer" in alice.roles
    assert alice.is_contractor is False


def test_bob_is_contractor():
    bob = seed_users()["bob"]
    assert "contractor" in bob.roles
    assert bob.is_contractor is True


def test_charlie_is_security():
    charlie = seed_users()["charlie"]
    assert "security_team" in charlie.roles


def test_identity_store_lookup():
    store = IdentityStore()
    assert store.get_user("alice") is not None
    assert store.get_user("nobody") is None


def test_all_roles_exist():
    expected = {"contractor", "engineer", "senior_engineer",
                "finance_analyst", "security_team",
                "compliance_officer", "admin"}
    assert set(ROLES.keys()) == expected


# -- Confluence connector tests ---------------------------------------

def test_confluence_list_resources():
    assert len(ConfluenceConnector().list_resources()) == 5


def test_confluence_alice_reads_eng_page():
    conn = ConfluenceConnector()
    alice = IdentityStore().get_user("alice")
    assert conn.check_membership(alice, "confluence:db-migration-plan") is True


def test_confluence_bob_denied_eng_page():
    conn = ConfluenceConnector()
    bob = IdentityStore().get_user("bob")
    assert conn.check_membership(bob, "confluence:db-migration-plan") is False


def test_confluence_charlie_reads_security():
    conn = ConfluenceConnector()
    charlie = IdentityStore().get_user("charlie")
    assert conn.check_membership(charlie, "confluence:q3-breach-report") is True


def test_confluence_bob_denied_security():
    conn = ConfluenceConnector()
    bob = IdentityStore().get_user("bob")
    assert conn.check_membership(bob, "confluence:q3-breach-report") is False


def test_confluence_acl_versioning():
    conn = ConfluenceConnector()
    old = conn.get_acl("confluence:payment-runbook")
    assert old.acl_version == 2
    new = conn.update_acl("confluence:payment-runbook", allowed_users=["a"])
    assert new.acl_version == 3


# -- Jira connector tests ---------------------------------------------

def test_jira_list_resources():
    assert len(JiraConnector().list_resources()) == 6


def test_jira_alice_reads_migration():
    conn = JiraConnector()
    alice = IdentityStore().get_user("alice")
    assert conn.check_membership(alice, "MIG-231") is True


def test_jira_bob_denied_migration():
    conn = JiraConnector()
    bob = IdentityStore().get_user("bob")
    assert conn.check_membership(bob, "MIG-231") is False


def test_jira_security_restricted():
    conn = JiraConnector()
    bob = IdentityStore().get_user("bob")
    alice = IdentityStore().get_user("alice")
    charlie = IdentityStore().get_user("charlie")
    assert conn.check_membership(bob, "SEC-101") is False
    assert conn.check_membership(alice, "SEC-101") is False
    assert conn.check_membership(charlie, "SEC-101") is True


def test_jira_help_visible_to_contractor():
    assert JiraConnector().check_membership(
        IdentityStore().get_user("bob"), "HELP-12") is True


# -- Slack connector tests --------------------------------------------

def test_slack_list_resources():
    assert len(SlackConnector().list_resources()) == 5


def test_slack_alice_in_public():
    conn = SlackConnector()
    alice = IdentityStore().get_user("alice")
    assert conn.check_membership(alice, "slack:db-migration-thread-992") is True


def test_slack_alice_not_in_leadership():
    conn = SlackConnector()
    alice = IdentityStore().get_user("alice")
    assert conn.check_membership(alice, "slack:leadership-thread-120") is False


def test_slack_alice_in_payment_incident():
    conn = SlackConnector()
    alice = IdentityStore().get_user("alice")
    assert conn.check_membership(alice, "slack:payment-incident-thread-45") is True


def test_slack_bob_denied_private():
    conn = SlackConnector()
    bob = IdentityStore().get_user("bob")
    assert conn.check_membership(bob, "slack:leadership-thread-120") is False
    assert conn.check_membership(bob, "slack:payment-incident-thread-45") is False


# -- GDrive connector tests -------------------------------------------

def test_gdrive_list_resources():
    assert len(GDriveConnector().list_resources()) == 4


def test_gdrive_alice_reads_postmortem():
    conn = GDriveConnector()
    alice = IdentityStore().get_user("alice")
    assert conn.check_membership(alice, "gdrive:payment-outage-postmortem") is True


def test_gdrive_bob_denied_postmortem():
    conn = GDriveConnector()
    bob = IdentityStore().get_user("bob")
    assert conn.check_membership(bob, "gdrive:payment-outage-postmortem") is False


def test_gdrive_onboarding_visible_to_all():
    conn = GDriveConnector()
    bob = IdentityStore().get_user("bob")
    alice = IdentityStore().get_user("alice")
    assert conn.check_membership(bob, "gdrive:onboarding-guide") is True
    assert conn.check_membership(alice, "gdrive:onboarding-guide") is True


# -- Cross-source tests ------------------------------------------------

def test_total_seed_resources():
    total = sum(len(c.list_resources()) for c in [
        ConfluenceConnector(), JiraConnector(),
        SlackConnector(), GDriveConnector()])
    assert total == 20


def test_connectors_return_correct_source():
    for res in ConfluenceConnector().list_resources():
        assert res.source == Source.CONFLUENCE
    for res in JiraConnector().list_resources():
        assert res.source == Source.JIRA
    for res in SlackConnector().list_resources():
        assert res.source == Source.SLACK
    for res in GDriveConnector().list_resources():
        assert res.source == Source.GDRIVE


def test_acl_version_increments():
    for conn in [ConfluenceConnector(), JiraConnector(),
                 SlackConnector(), GDriveConnector()]:
        res = conn.list_resources()[0]
        old = res.acl.acl_version
        conn.update_acl(res.resource_id, allowed_users=["x"])
        assert conn.get_acl(res.resource_id).acl_version == old + 1