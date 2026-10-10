"""Natural-language audit query parser.

Turns a plain-English compliance question — "what did alice access last
week?" — into a structured :class:`AuditQuery`. This backs the audit
explorer's search box so an inspector can type a question instead of
setting filters by hand.

Design: deterministic first. The parser uses explicit lexical rules (known
user ids/names, a small set of time phrases, allow/deny keywords). It needs
no model, so it works offline and gives the same answer every time — which is
exactly what you want for an audit tool. An optional LLM can be layered on top
by the caller for fuzzier phrasing, but the deterministic parser is always the
fallback (and the default), so the feature never depends on network/LLM
availability.

The parser is intentionally conservative: anything it cannot confidently map
is left unset (the query simply doesn't filter on it) rather than guessed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from backend.audit.audit_query import AuditQuery


@dataclass
class ParsedQuery:
    """Result of parsing a natural-language audit question.

    Attributes:
        query: The structured AuditQuery to run.
        interpretation: Human-readable description of what was understood,
            shown back to the inspector so the parse is transparent.
        matched: True if ANY criterion was extracted. A question that parsed
            to nothing (all filters empty) is reported so the UI can warn
            rather than silently returning the entire log.
    """

    query: AuditQuery
    interpretation: str = ""
    matched: bool = False
    parts: list[str] = field(default_factory=list)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _start_of_day(dt: datetime) -> datetime:
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def parse_time_window(text: str, now: datetime | None = None):
    """Extract a (since, until, label) time window from `text`.

    Recognizes: today, yesterday, last/past N days|weeks|months, last week,
    last month, this week, this month. Returns (None, None, "") if no time
    phrase is found.
    """
    now = now or _now()
    t = text.lower()

    # "last N days/weeks/months" or "past N ..."
    m = re.search(r"\b(?:last|past)\s+(\d+)\s*(day|week|month)s?\b", t)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        days = n * {"day": 1, "week": 7, "month": 30}[unit]
        since = _start_of_day(now - timedelta(days=days))
        return since, None, f"in the last {n} {unit}{'s' if n != 1 else ''}"

    if re.search(r"\b(today)\b", t):
        return _start_of_day(now), None, "today"

    if re.search(r"\b(yesterday)\b", t):
        start = _start_of_day(now - timedelta(days=1))
        end = _start_of_day(now) - timedelta(seconds=1)
        return start, end, "yesterday"

    # "last week" / "past week" (singular) → 7 days.
    if re.search(r"\b(?:last|past|this)\s+week\b", t):
        since = _start_of_day(now - timedelta(days=7))
        return since, None, "in the last week"

    # "last month" / "past month" / "this month" → 30 days.
    if re.search(r"\b(?:last|past|this)\s+month\b", t):
        since = _start_of_day(now - timedelta(days=30))
        return since, None, "in the last month"

    return None, None, ""


def parse_decision(text: str):
    """Extract a decision filter (allow/deny) from `text`, or None."""
    t = text.lower()
    if re.search(r"\b(denied|denies|blocked|refused|rejected|couldn'?t access|was denied)\b", t):
        return "deny", "that were denied"
    if re.search(r"\b(allow(?:ed)?|access(?:ed)?|read|view(?:ed)?|retrieved?|saw|got access)\b", t):
        return "allow", "that were allowed"
    return None, ""


def resolve_user(text: str, user_ids: list[str], names: dict[str, str] | None = None):
    """Match a known user id or display name in `text`.

    `user_ids` is the authoritative list (e.g. ["alice", "bob", ...]).
    `names` optionally maps user_id -> display name for name-based matching.
    Returns (user_id, label) or (None, "").
    """
    t = text.lower()
    # Prefer an exact user-id word match.
    for uid in user_ids:
        if re.search(rf"\b{re.escape(uid.lower())}\b", t):
            return uid, uid
    # Fall back to display-name first-name match.
    if names:
        for uid, name in names.items():
            if not name:
                continue
            for token in name.lower().split():
                if len(token) >= 3 and re.search(rf"\b{re.escape(token)}\b", t):
                    return uid, name
    return None, ""


def parse(
    text: str,
    user_ids: list[str],
    names: dict[str, str] | None = None,
    now: datetime | None = None,
) -> ParsedQuery:
    """Parse a natural-language audit question into a ParsedQuery.

    Deterministic and conservative: only sets a filter when it is confident.
    """
    text = (text or "").strip()
    parts: list[str] = []

    uid, user_label = resolve_user(text, user_ids, names)
    since, until, time_label = parse_time_window(text, now=now)
    decision, dec_label = parse_decision(text)

    # A resource substring in quotes, e.g. 'payment' in: what about "payment"?
    resource_contains = None
    qm = re.search(r"[\"'“]([^\"'”]{2,})[\"'”]", text)
    if qm:
        resource_contains = qm.group(1).strip()

    if uid:
        parts.append(f"user = {user_label}")
    if decision:
        parts.append(dec_label)
    if time_label:
        parts.append(time_label)
    if resource_contains:
        parts.append(f'resource contains "{resource_contains}"')

    query = AuditQuery(
        user_id=uid,
        decision=decision,
        resource_contains=resource_contains,
        since=since,
        until=until,
    )

    matched = bool(uid or decision or time_label or resource_contains)
    if matched:
        subject = user_label if uid else "all users"
        action = dec_label.replace("that were ", "") if decision else "activity"
        when = time_label or "across the whole log"
        interpretation = f"Showing {action} for {subject} {when}.".replace("  ", " ")
    else:
        interpretation = (
            "Couldn't extract a filter from that question — showing the full "
            "log. Try naming a user and a time window, e.g. "
            "\"what did alice access last week?\""
        )

    return ParsedQuery(
        query=query,
        interpretation=interpretation,
        matched=matched,
        parts=parts,
    )
