"""Audit explorer behaviour driven by demo feedback.

- Permission changes (revoke/grant) are part of the tamper-evident history.
- Every audit query re-verifies the on-disk log, so a hand-edit shows up on
  the next refresh without pressing a verify button — and a refresh can never
  flip a tampered log back to "verified".
- Plain-English search returns the structured filters it resolved to, so the
  UI can fill the filter fields instead of describing them in prose.
"""

import json

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app

DIANA = {"X-User-Id": "diana"}
FRANK = {"X-User-Id": "frank"}
PLAN = "confluence:db-migration-plan"


@pytest.fixture()
def log_path(tmp_path):
    return tmp_path / "audit_log.json"


@pytest.fixture()
def client(log_path, monkeypatch):
    monkeypatch.setenv("TIANQUAN_AUDIT_LOG", str(log_path))
    return TestClient(create_app())


def _query(client, user="alice", q="What is the status of the database migration?"):
    return client.post("/query", json={"user_id": user, "question": q, "k": 20}).json()


# -- permission changes in the audit trail ---------------------------------

def test_revoke_is_audited_with_actor_and_version(client):
    client.post("/admin/revoke", headers=FRANK, json={
        "resource_id": PLAN, "subject": "engineer", "subject_kind": "role"})
    events = client.get("/audit", headers=DIANA).json()["events"]
    change = [e for e in events if e["action"] == "acl_revoke"]
    assert len(change) == 1
    e = change[0]
    assert e["user_id"] == "frank"
    assert e["resource_id"] == PLAN
    assert e["decision"] == "change"
    assert "role:engineer" in e["detail"] and "v1 -> v2" in e["detail"]


def test_grant_is_audited(client):
    client.post("/admin/grant", headers=FRANK, json={
        "resource_id": PLAN, "subject": "bob", "subject_kind": "user"})
    events = client.get("/audit", headers=DIANA).json()["events"]
    assert [e["action"] for e in events] == ["acl_grant"]


def test_permission_changes_do_not_count_as_allow_or_deny(client):
    client.post("/admin/revoke", headers=FRANK, json={
        "resource_id": PLAN, "subject": "engineer", "subject_kind": "role"})
    r = client.get("/audit", headers=DIANA).json()
    assert r["count"] == 1 and r["allow_count"] == 0 and r["deny_count"] == 0
