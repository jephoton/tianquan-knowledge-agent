"""Tests for the M8 FastAPI layer.

Run with: python -m pytest tests/test_m8_api.py -v

Uses FastAPI's TestClient (in-process, no server). Each test gets a fresh app
so state (audit chain, ACLs) is isolated.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app


@pytest.fixture()
def client():
    return TestClient(create_app())


# -- Meta --------------------------------------------------------------

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_users_lists_seed_personas(client):
    r = client.get("/users")
    assert r.status_code == 200
    ids = {u["user_id"] for u in r.json()}
    assert {"alice", "bob", "charlie"} <= ids


# -- /query ------------------------------------------------------------

def test_query_allowed_user_gets_answer(client):
    r = client.post("/query", json={
        "user_id": "alice", "question": "database migration status", "k": 20,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["no_access"] is False
    assert len(body["citations"]) >= 1
    assert body["allow_count"] >= 1
    assert body["audit_chain_head"]


def test_query_denied_user_no_leak(client):
    r = client.post("/query", json={
        "user_id": "bob", "question": "security breach incident report", "k": 20,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["no_access"] is True
    assert body["citations"] == []
    assert "breach" not in body["answer"].lower()


def test_query_unknown_user_404(client):
    r = client.post("/query", json={"user_id": "nobody", "question": "hi"})
    assert r.status_code == 404


def test_query_decisions_include_reason_and_version(client):
    r = client.post("/query", json={
        "user_id": "alice", "question": "database migration payment", "k": 20,
    })
    decisions = r.json()["decisions"]
    assert decisions
    for d in decisions:
        assert "reason" in d and d["reason"]
        assert "acl_version" in d


# -- /audit ------------------------------------------------------------

def test_audit_records_after_query(client):
    client.post("/query", json={"user_id": "alice", "question": "database migration", "k": 20})
    r = client.get("/audit")
    body = r.json()
    assert body["count"] >= 1
    assert body["chain_valid"] is True


def test_audit_filter_by_user(client):
    client.post("/query", json={"user_id": "alice", "question": "database migration", "k": 10})
    client.post("/query", json={"user_id": "bob", "question": "security breach", "k": 10})
    r = client.get("/audit", params={"user_id": "bob"})
    events = r.json()["events"]
    assert events
    assert all(e["user_id"] == "bob" for e in events)


def test_audit_verify_endpoint(client):
    client.post("/query", json={"user_id": "alice", "question": "database migration", "k": 10})
    r = client.get("/audit/verify")
    body = r.json()
    assert body["valid"] is True
    assert body["length"] >= 1


# -- /admin (Demo 3 over HTTP) ----------------------------------------

def test_revoke_then_query_excludes_resource(client):
    q = {"user_id": "alice", "question": "database migration plan", "k": 20}

    before = client.post("/query", json=q).json()
    before_ids = [c["resource_id"] for c in before["citations"]]
    assert "confluence:db-migration-plan" in before_ids

    rev = client.post("/admin/revoke", json={
        "resource_id": "confluence:db-migration-plan",
        "subject": "engineer", "subject_kind": "role",
    })
    assert rev.status_code == 200
    assert rev.json()["new_version"] == rev.json()["previous_version"] + 1

    after = client.post("/query", json=q).json()
    after_ids = [c["resource_id"] for c in after["citations"]]
    assert "confluence:db-migration-plan" not in after_ids


def test_grant_restores_access(client):
    q = {"user_id": "alice", "question": "database migration plan", "k": 20}
    client.post("/admin/revoke", json={
        "resource_id": "confluence:db-migration-plan",
        "subject": "alice", "subject_kind": "user",
    })
    denied = client.post("/query", json=q).json()
    assert "confluence:db-migration-plan" not in \
        [c["resource_id"] for c in denied["citations"]]

    client.post("/admin/grant", json={
        "resource_id": "confluence:db-migration-plan",
        "subject": "alice", "subject_kind": "user",
    })
    restored = client.post("/query", json=q).json()
    assert "confluence:db-migration-plan" in \
        [c["resource_id"] for c in restored["citations"]]


def test_revoke_unknown_resource_404(client):
    r = client.post("/admin/revoke", json={
        "resource_id": "nope:nothing", "subject": "alice", "subject_kind": "user",
    })
    assert r.status_code == 404


def test_admin_change_reports_version_transition(client):
    r = client.post("/admin/revoke", json={
        "resource_id": "MIG-231", "subject": "engineer", "subject_kind": "role",
    })
    body = r.json()
    assert body["version_transition"] == \
        f"v{body['previous_version']} -> v{body['new_version']}"
