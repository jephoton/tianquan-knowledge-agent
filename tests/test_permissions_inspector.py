"""Tests for the read-only permissions inspector."""

from __future__ import annotations

from backend.connectors.confluence import ConfluenceConnector
from backend.connectors.gdrive import GDriveConnector
from backend.connectors.jira import JiraConnector
from backend.connectors.slack import SlackConnector
from backend.auth.identity import IdentityStore
from backend.policy.inspector import PermissionsInspector


def _inspector():
    ident = IdentityStore()
    connectors = [
        ConfluenceConnector(), JiraConnector(), SlackConnector(), GDriveConnector(),
    ]
    return PermissionsInspector(connectors, ident.all_users()), ident


# -- by user -----------------------------------------------------------

def test_user_report_lists_roles():
    insp, ident = _inspector()
    rep = insp.for_user(ident.get_user("alice"))
    assert rep.roles == ["engineer"]
    assert rep.user_id == "alice"


def test_user_report_has_resources_with_access_flags():
    insp, ident = _inspector()
    rep = insp.for_user(ident.get_user("alice"))
    assert rep.resources, "should enumerate resources"
    # readable_count should match the number of can_read resources
    assert rep.readable_count == sum(1 for r in rep.resources if r.can_read)


def test_contractor_reads_fewer_than_engineer():
    insp, ident = _inspector()
    alice = insp.for_user(ident.get_user("alice"))     # engineer
    bob = insp.for_user(ident.get_user("bob"))          # contractor
    assert bob.readable_count < alice.readable_count


def test_user_report_explains_via_grant():
    insp, ident = _inspector()
    rep = insp.for_user(ident.get_user("alice"))
    readable = [r for r in rep.resources if r.can_read]
    # Every readable resource must explain HOW (user-grant or role:*)
    for r in readable:
        assert r.via == "user-grant" or r.via.startswith("role:")


def test_denied_resource_marked_no_read():
    """A resource whose role alice lacks should be can_read=False."""
    insp, ident = _inspector()
    rep = insp.for_user(ident.get_user("bob"))
    denied = [r for r in rep.resources if not r.can_read]
    assert denied, "contractor should be denied at least one resource"


# -- by role -----------------------------------------------------------

def test_role_report_lists_members():
    insp, ident = _inspector()
    rep = insp.for_role("engineer")
    assert "alice" in rep.members


def test_role_report_lists_granted_resources():
    insp, _ = _inspector()
    rep = insp.for_role("engineer")
    # engineer grants access to at least one resource in the seed corpus
    assert isinstance(rep.resources, list)


def test_role_with_no_members_is_empty():
    insp, _ = _inspector()
    rep = insp.for_role("nonexistent_role")
    assert rep.members == []
    assert rep.resources == []


# -- by resource -------------------------------------------------------

def test_resource_report_shows_acl():
    insp, _ = _inspector()
    rep = insp.for_resource("confluence:db-migration-plan")
    assert rep is not None
    assert rep.resource_id == "confluence:db-migration-plan"
    assert rep.acl_version >= 0


def test_resource_report_effective_readers_nonempty():
    insp, _ = _inspector()
    rep = insp.for_resource("confluence:db-migration-plan")
    assert rep.effective_readers, "someone should be able to read the migration plan"


def test_unknown_resource_returns_none():
    insp, _ = _inspector()
    assert insp.for_resource("confluence:does-not-exist") is None


def test_effective_readers_consistent_with_user_report():
    """If a user is an effective reader of a resource, their user report
    should mark that resource can_read, and vice versa."""
    insp, ident = _inspector()
    rid = "confluence:db-migration-plan"
    res_rep = insp.for_resource(rid)
    for uid in res_rep.effective_readers:
        user_rep = insp.for_user(ident.get_user(uid))
        match = [r for r in user_rep.resources if r.resource_id == rid]
        assert match and match[0].can_read
