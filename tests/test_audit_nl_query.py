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
