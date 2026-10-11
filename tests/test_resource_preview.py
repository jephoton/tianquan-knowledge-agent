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



# -- A new connector gets the same fail-closed permission checks ----------
#
# Regression: sources without their own rule (e.g. the upload connector) used
# to hit "unknown_source_default_allow" and skip the ACL entirely.

def _upload(client, roles):
    return client.post("/upload", headers={"X-User-Id": "frank"}, json={
        "resource_id": "upload:q4-incident",
        "title": "Q4 Production Incident Report",
        "content": "On 2026-10-05 the card-issuing service failed over to the DR "
                   "region after an expired TLS certificate on the issuer gateway.",
        "allowed_roles": roles,
    })


def _cites(client, user):
    r = client.post("/query", json={"user_id": user, "k": 20,
        "question": "What happened in the Q4 production incident?"}).json()
    return {c["resource_id"] for c in r["citations"]}


def test_uploaded_document_honours_its_allowed_roles(client):
    assert _upload(client, ["security_team", "admin"]).status_code == 200
    assert "upload:q4-incident" in _cites(client, "charlie")      # security_team
    assert "upload:q4-incident" not in _cites(client, "alice")    # engineer
    assert "upload:q4-incident" not in _cites(client, "bob")      # contractor


def test_unknown_source_is_denied_by_default():
    from backend.auth.identity import IdentityStore
    from backend.policy.permission_mapping import check_source_specific
    from backend.models import Resource, ACL, Source
    from datetime import datetime, timezone
    r = Resource(source=Source.UPLOAD, resource_id="x", title="t", content="c",
                 updated_at=datetime.now(timezone.utc),
                 acl=ACL(acl_version=1, allowed_users=[], allowed_roles=[],
                         denied_users=[], source_permissions={}))
    allowed, _ = check_source_specific(IdentityStore().get_user("frank"), r)
    assert allowed is False   # no grant on the ACL -> deny, even for admin
