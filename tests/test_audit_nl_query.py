"""Tests for the deterministic natural-language audit query parser."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.audit import nl_query

USER_IDS = ["alice", "bob", "charlie", "diana", "jdoe", "erin", "frank"]
NAMES = {
    "alice": "Alice Chen",
    "bob": "Bob Contractor",
    "charlie": "Charlie Ng",
    "diana": "Diana Tan",
    "jdoe": "John Doe",
    "erin": "Erin Wong",
    "frank": "Frank Lim",
}

NOW = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)


def _parse(q):
    return nl_query.parse(q, user_ids=USER_IDS, names=NAMES, now=NOW)


# -- user resolution ---------------------------------------------------

def test_resolves_user_by_id():
    p = _parse("what did alice access last week?")
    assert p.query.user_id == "alice"
    assert p.matched


def test_resolves_user_by_first_name():
    p = _parse("show me everything John did")
    assert p.query.user_id == "jdoe"


def test_unknown_user_leaves_user_unset():
    p = _parse("what did zelda do last week")
    assert p.query.user_id is None
    # still matched on the time window
    assert p.matched


# -- time windows ------------------------------------------------------

def test_last_week():
    p = _parse("what did alice access last week?")
    assert p.query.since == NOW.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=7)
    assert p.query.until is None


def test_last_n_days():
    p = _parse("alice activity in the last 3 days")
    expected = (NOW - timedelta(days=3)).replace(hour=0, minute=0, second=0, microsecond=0)
    assert p.query.since == expected


def test_yesterday_has_bounded_window():
    p = _parse("what did bob do yesterday")
    assert p.query.since is not None
    assert p.query.until is not None
    assert p.query.until < NOW


def test_today():
    p = _parse("alice today")
    assert p.query.since == NOW.replace(hour=0, minute=0, second=0, microsecond=0)


def test_last_month():
    p = _parse("charlie last month")
    expected = (NOW - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)
    assert p.query.since == expected


def test_no_time_phrase_leaves_window_unset():
    p = _parse("what did alice access")
    assert p.query.since is None
    assert p.query.until is None


# -- decision ----------------------------------------------------------

def test_denied_keyword():
    p = _parse("what was alice denied last week")
    assert p.query.decision == "deny"


def test_accessed_keyword():
    p = _parse("what did alice access last week")
    assert p.query.decision == "allow"


# -- resource substring ------------------------------------------------

def test_quoted_resource_substring():
    p = _parse('did alice touch anything about "payment" last week')
    assert p.query.resource_contains == "payment"


# -- interpretation / empty -------------------------------------------

def test_interpretation_describes_parse():
    p = _parse("what did alice access last week?")
    assert "alice" in p.interpretation.lower()
    assert "week" in p.interpretation.lower()


def test_empty_question_matches_nothing():
    p = _parse("")
    assert not p.matched
    assert p.query.user_id is None
    assert p.query.since is None


def test_gibberish_matches_nothing_and_warns():
    p = _parse("asdfghjkl qwerty")
    assert not p.matched
    assert "couldn't" in p.interpretation.lower() or "could not" in p.interpretation.lower()


# -- resource phrases resolved against the catalog ---------------------
#
# A compliance question names resources the way people do — "the q3 breach
# report", "the ENG Confluence space" — not by resource id. The parser
# resolves those phrases against the live resource catalog, and says plainly
# which parts of the question it could not map instead of silently dropping
# them (an audit tool must never answer a different question than was asked).

CATALOG = [
    nl_query.CatalogEntry("confluence:db-migration-plan", "Database Migration Project - Q3 Plan", "confluence", "ENG"),
    nl_query.CatalogEntry("confluence:payment-runbook", "Payment Service Incident Runbook", "confluence", "ENG"),
    nl_query.CatalogEntry("confluence:q3-breach-report", "Q3 Security Incident Report - Data Breach", "confluence", "SEC"),
    nl_query.CatalogEntry("confluence:q3-budget", "Q3 Budget Report - Finance", "confluence", "FIN"),
    nl_query.CatalogEntry("PAY-460", "[PAY-460] Re-enable circuit breaker on payment-gateway client", "jira", "PAY"),
    nl_query.CatalogEntry("SEC-101", "[SEC-101] Security: Leaked credential in staging deployment", "jira", "SEC"),
    nl_query.CatalogEntry("slack:payment-general-thread-7", "#payment-general - Thread: Circuit breaker follow-up", "slack", "payment-general"),
]


def _parse_c(q):
    return nl_query.parse(q, user_ids=USER_IDS, names=NAMES, now=NOW, catalog=CATALOG)


def test_resource_phrase_resolves_to_resource():
    p = _parse_c("who retrieved the q3 breach report")
    assert p.query.resource_ids == {"confluence:q3-breach-report"}
    assert p.query.decision == "allow"
    assert p.unparsed == []


def test_named_space_filters_to_its_pages():
    p = _parse_c("what did alice access in the ENG confluence space")
    assert p.query.resource_ids == {
        "confluence:db-migration-plan", "confluence:payment-runbook",
    }


def test_jira_project_filters_to_its_issues():
    p = _parse_c("show denied events in the SEC project")
    assert p.query.resource_ids == {"SEC-101"}


def test_source_mention_filters_to_that_source():
    p = _parse_c("what did jdoe read in jira")
    assert p.query.resource_ids == {"PAY-460", "SEC-101"}


def test_handbook_example_unknown_space_is_reported_not_dropped():
    """The handbook's example names a 'payment-gateway' Confluence space; the
    seed data has no such space. Say so, and fall back to Confluence pages
    about it — never silently ignore the constraint."""
    p = _parse_c(
        "Show me everything user jdoe accessed related to the payment-gateway "
        "Confluence space in the last 30 days"
    )
    assert p.query.user_id == "jdoe"
    assert p.query.since is not None
    assert p.query.resource_ids == {"confluence:payment-runbook"}
    assert "payment-gateway" in p.interpretation
    assert "no confluence space" in p.interpretation.lower()


def test_unrecognized_words_are_reported():
    p = _parse_c("what did alice access about the zorblax initiative")
    assert p.query.user_id == "alice"
    assert "zorblax" in p.unparsed
    assert "zorblax" in p.interpretation


def test_resource_ids_filter_applies_to_events():
    from backend.audit.audit_query import AuditQuery
    from backend.audit.event_schema import AuditEvent
    q = AuditQuery(resource_ids={"r1"})
    hit = AuditEvent(event_id="1", user_id="a", query_id="q", action="read",
                     decision="allow", reason="", acl_version=1,
                     policy_version=1, resource_id="r1")
    miss = AuditEvent(event_id="2", user_id="a", query_id="q", action="read",
                      decision="allow", reason="", acl_version=1,
                      policy_version=1, resource_id="r2")
    assert q.matches(hit) and not q.matches(miss)
