"""Tests for GET /resource/{id} — the source-preview panel's backend.

The preview returns a source's raw content, so it is an access-control and
audit boundary in its own right:

- identity comes from the X-User-Id header (like every privileged route), not
  a caller-chosen query parameter;
- it requires the `export` permission — once you can read the raw source you
  can copy it out, so viewing it IS exporting (server-enforced, not cosmetic);
- every preview, allowed or denied, is written to the audit trail;
- "denied" and "does not exist" are indistinguishable (no existence oracle).
"""

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("TIANQUAN_AUDIT_LOG", str(tmp_path / "audit_log.jsonl"))
    return TestClient(create_app())


BREACH = "confluence:q3-breach-report"


def _audit(client):
    return client.get("/audit", headers={"X-User-Id": "diana"}).json()["events"]


def test_authorized_preview_returns_content(client):
    r = client.get(f"/resource/{BREACH}", headers={"X-User-Id": "charlie"})
    assert r.status_code == 200
    assert r.json()["resource_id"] == BREACH
    assert r.json()["content"]


def test_preview_requires_identity_header(client):
    # A caller-supplied user_id query parameter is not an identity.
    r = client.get(f"/resource/{BREACH}?user_id=charlie")
    assert r.status_code == 401


def test_preview_requires_export_permission(client):
    # alice can READ the migration plan but lacks `export` — viewing the raw
    # source is exporting, so the server refuses even though the UI hides it.
    r = client.get("/resource/confluence:db-migration-plan",
                   headers={"X-User-Id": "alice"})
    assert r.status_code == 403


def test_denied_and_nonexistent_are_indistinguishable(client):
    # jdoe holds `export` but is not cleared for the breach report.
    denied = client.get(f"/resource/{BREACH}", headers={"X-User-Id": "jdoe"})
    missing = client.get("/resource/confluence:does-not-exist",
                         headers={"X-User-Id": "jdoe"})
    assert denied.status_code == missing.status_code == 404
    assert denied.json() == missing.json()


def test_allowed_preview_is_audited(client):
    client.get(f"/resource/{BREACH}", headers={"X-User-Id": "charlie"})
    events = [e for e in _audit(client)
              if e["user_id"] == "charlie" and e["resource_id"] == BREACH]
    assert len(events) == 1
    assert events[0]["decision"] == "allow"
    assert events[0]["detail"] == "source_preview"


def test_denied_and_missing_previews_are_audited(client):
    client.get(f"/resource/{BREACH}", headers={"X-User-Id": "jdoe"})
    client.get("/resource/confluence:does-not-exist", headers={"X-User-Id": "jdoe"})
    events = [e for e in _audit(client) if e["user_id"] == "jdoe"]
    assert {e["resource_id"] for e in events} == {BREACH, "confluence:does-not-exist"}
    assert all(e["decision"] == "deny" for e in events)


# -- /audit/search resolves resource phrases against the live catalog ------

def test_audit_search_resolves_resource_phrase(client):
    client.post("/query", json={"user_id": "alice", "k": 20,
        "question": "What is the status of the database migration?"})
    client.post("/query", json={"user_id": "charlie", "k": 20,
        "question": "Show me the Q3 security incident report from the breach"})
    r = client.get("/audit/search", headers={"X-User-Id": "diana"},
                   params={"q": "who retrieved the q3 breach report"}).json()
    assert r["count"] >= 1
    assert {e["resource_id"] for e in r["events"]} == {BREACH}
    assert r["unparsed"] == []


def test_audit_search_reports_unparsed_words(client):
    r = client.get("/audit/search", headers={"X-User-Id": "diana"},
                   params={"q": "what did alice access about the zorblax initiative"}).json()
    assert "zorblax" in r["unparsed"]
