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
    return tmp_path / "audit_log.jsonl"


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


# -- integrity is checked on every audit query ----------------------------

def test_empty_log_reads_as_verified(client):
    assert client.get("/audit", headers=DIANA).json()["chain_valid"] is True


def test_hand_edit_shows_on_next_refresh_and_stays_red(client, log_path):
    _query(client)
    assert client.get("/audit", headers=DIANA).json()["chain_valid"] is True

    data = [json.loads(l) for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    data[0]["decision"] = "deny" if data[0]["decision"] == "allow" else "allow"
    log_path.write_text("".join(json.dumps(e) + "\n" for e in data), encoding="utf-8")

    # No verify button: any audit query reports it, whatever the filters.
    r1 = client.get("/audit", headers=DIANA).json()
    r2 = client.get("/audit", headers=DIANA, params={"user_id": "bob"}).json()
    r3 = client.get("/audit/search", headers=DIANA, params={"q": "what did alice access"}).json()
    for r in (r1, r2, r3):
        assert r["chain_valid"] is False
        assert "tampered_event_at_0" in r["chain_status"]


def test_deleted_log_file_is_tamper(client, log_path):
    _query(client)
    log_path.unlink()
    assert client.get("/audit", headers=DIANA).json()["chain_valid"] is False


# -- plain-English search returns the filters it resolved to --------------

def test_search_returns_structured_filters(client):
    r = client.get("/audit/search", headers=DIANA, params={
        "q": "what did alice access in the ENG confluence space in the last 7 days"}).json()
    f = r["filters"]
    assert f["user_id"] == "alice"
    assert f["decision"] == "allow"
    assert len(f["since"]) == 10 and f["until"] == ""  # YYYY-MM-DD
    assert set(f["resource"].split(", ")) == {
        "confluence:db-migration-plan", "confluence:payment-runbook",
        "confluence:auth-service-design",
    }


def test_resource_filter_accepts_comma_separated_alternatives(client):
    _query(client)
    r = client.get("/audit", headers=DIANA, params={
        "resource_contains": "MIG-231, MIG-232"}).json()
    assert r["count"] >= 2
    assert {e["resource_id"] for e in r["events"]} <= {"MIG-231", "MIG-232"}


def test_filled_filters_reproduce_the_search(client):
    _query(client)
    s = client.get("/audit/search", headers=DIANA, params={
        "q": "what did alice access in jira"}).json()
    f = s["filters"]
    params = {k: v for k, v in {
        "user_id": f["user_id"], "decision": f["decision"],
        "resource_contains": f["resource"], "since": f["since"],
    }.items() if v}
    r = client.get("/audit", headers=DIANA, params=params).json()
    assert r["count"] == s["count"]
