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
        unparsed: Words of the question that mapped to nothing. They are
            reported back (never silently dropped) so the inspector knows the
            result may be broader than what they asked.
    """

    query: AuditQuery
    interpretation: str = ""
    matched: bool = False
    parts: list[str] = field(default_factory=list)
    unparsed: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CatalogEntry:
    """A resource the parser can resolve phrases against.

    `container` is the resource's native grouping: the Confluence space, Jira
    project, Slack channel, or Drive folder.
    """

    resource_id: str
    title: str
    source: str
    container: str = ""


# Platform names -> source value.
_SOURCE_WORDS = {
    "confluence": "confluence", "jira": "jira", "slack": "slack",
    "gdrive": "gdrive", "drive": "gdrive",
}

# Container nouns -> the source whose native grouping they name.
_CONTAINER_WORDS = {"space": "confluence", "project": "jira", "channel": "slack"}

# Words that carry no filter meaning of their own (question scaffolding, the
# vocabulary the user/time/decision rules already handle, generic nouns).
_FILLER = frozenset({
    "show", "me", "everything", "anything", "all", "what", "did", "does", "do",
    "who", "whom", "which", "user", "users", "related", "relating", "to",
    "the", "a", "an", "in", "on", "of", "for", "about", "events", "event",
    "any", "that", "were", "was", "is", "are", "by", "from", "with", "has",
    "have", "had", "happened", "list", "give", "find", "there", "touch",
    "touched", "their", "his", "her", "its", "and", "or", "at", "into",
    "ever", "since", "when", "how", "many", "times", "it", "they", "them",
    "access", "accessed", "accesses", "allowed", "allow", "read", "reads",
    "viewed", "view", "views", "retrieved", "retrieve", "saw", "see", "got",
    "denied", "deny", "denies", "blocked", "refused", "rejected", "couldn",
    "t", "last", "past", "this", "week", "weeks", "month", "months", "day",
    "days", "today", "yesterday", "doc", "docs", "document", "documents",
    "page", "pages", "ticket", "tickets", "issue", "issues", "thread",
    "threads", "file", "files", "resource", "resources", "anyone", "someone",
})

_WORD_RE = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*")


def _words(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def _title_words(entry: CatalogEntry) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", f"{entry.title} {entry.resource_id}".lower()))


def _best_matches(
    topic: list[str], entries: list[CatalogEntry],
) -> tuple[set[str], set[str]]:
    """Resolve topic words to the catalog entries matching the most of them.

    Returns (resource_ids, words that matched). Ties keep every entry with the
    top score, so "q3 report" matches both Q3 reports rather than guessing.
    """
    best = 0
    winners: list[CatalogEntry] = []
    for e in entries:
        score = len(set(topic) & _title_words(e))
        if score > best:
            best, winners = score, [e]
        elif score == best and score > 0:
            winners.append(e)
    if best == 0:
        return set(), set()
    used = set(topic) & set().union(*(_title_words(e) for e in winners))
    return {e.resource_id for e in winners}, used


def resolve_resources(
    text: str, catalog: list[CatalogEntry], consumed: set[str],
) -> tuple[set[str] | None, str, list[str], list[str]]:
    """Resolve source / container / topic phrases in `text` to resource ids.

    Returns (resource_ids or None, label, notes, unparsed). `consumed` holds
    words other rules already explained (user names etc.).
    """
    words = [w for w in _words(text) if w not in consumed]
    sources = {_SOURCE_WORDS[w] for w in words if w in _SOURCE_WORDS}
    pool = [e for e in catalog if not sources or e.source in sources]
    explained = {w for w in words if w in _SOURCE_WORDS}
    notes: list[str] = []
    label = ", ".join(sorted(sources)) if sources else ""
    resolved: set[str] | None = {e.resource_id for e in pool} if sources else None

    # Container phrase: "the ENG confluence space", "SEC project", "space ENG".
    for i, w in enumerate(words):
        if w not in _CONTAINER_WORDS:
            continue
        csource = _CONTAINER_WORDS[w]
        j = i - 1
        while j >= 0 and words[j] in _SOURCE_WORDS:
            j -= 1
        name = words[j] if j >= 0 and words[j] not in _FILLER else ""
        if not name and i + 1 < len(words) and words[i + 1] not in _FILLER:
            name = words[i + 1]
        explained.add(w)
        if not name:
            continue
        explained.add(name)
        in_container = [
            e for e in catalog
            if e.source == csource and e.container.lower() == name
        ]
        if in_container:
            resolved = {e.resource_id for e in in_container}
            label = f"the {name.upper()} {csource} {w}"
        else:
            # No such container: say so, and fall back to that source's
            # resources about the name rather than dropping the constraint.
            fallback = [e for e in catalog if e.source == csource]
            ids, _ = _best_matches(re.findall(r"[a-z0-9]+", name), fallback)
            if ids:
                resolved = ids
                label = f"{csource} resources about '{name}'"
                notes.append(
                    f"No {csource} {w} named '{name}' — matched {csource} "
                    f"resources about it instead: {', '.join(sorted(ids))}."
                )
            else:
                notes.append(f"No {csource} {w} named '{name}' — ignored.")
        break

    # Topic words: whatever is left, matched against titles/ids.
    topic: list[str] = []
    for w in words:
        if w in explained or w in _FILLER or w.isdigit():
            continue
        topic.extend(re.findall(r"[a-z0-9]+", w))
    unparsed: list[str] = []
    if topic:
        scope = [e for e in catalog if resolved is None or e.resource_id in resolved]
        ids, used = _best_matches(topic, scope)
        if ids:
            resolved = ids
            label = (
                ", ".join(sorted(ids)) if len(ids) <= 3
                else f"{len(ids)} resources matching '{' '.join(sorted(used))}'"
            )
        unparsed = [w for w in topic if w not in used]
    return resolved, label, notes, unparsed


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
    catalog: list[CatalogEntry] | None = None,
) -> ParsedQuery:
    """Parse a natural-language audit question into a ParsedQuery.

    Deterministic and conservative: only sets a filter when it is confident.
    With a `catalog`, resource phrases ("the q3 breach report", "the ENG
    Confluence space") resolve to resource ids, and any words that map to
    nothing are reported in `unparsed`.
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

    # Words the user rule explained (id and display-name tokens).
    consumed: set[str] = set()
    if uid:
        consumed.add(uid.lower())
        consumed.update(((names or {}).get(uid) or "").lower().split())
    unquoted = text[:qm.start()] + text[qm.end():] if qm else text

    resource_ids: set[str] | None = None
    resource_label, notes, unparsed = "", [], []
    if catalog is not None:
        resource_ids, resource_label, notes, unparsed = resolve_resources(
            unquoted, catalog, consumed,
        )

    if uid:
        parts.append(f"user = {user_label}")
    if decision:
        parts.append(dec_label)
    if time_label:
        parts.append(time_label)
    if resource_contains:
        parts.append(f'resource contains "{resource_contains}"')
    if resource_ids is not None:
        parts.append(f"resource = {resource_label}")

    query = AuditQuery(
        user_id=uid,
        decision=decision,
        resource_contains=resource_contains,
        resource_ids=resource_ids,
        since=since,
        until=until,
    )

    matched = bool(
        uid or decision or time_label or resource_contains
        or resource_ids is not None
    )
    if matched:
        subject = user_label if uid else "all users"
        action = dec_label.replace("that were ", "") if decision else "activity"
        on = f" on {resource_label}" if resource_ids is not None else ""
        when = time_label or "across the whole log"
        interpretation = f"Showing {action} for {subject}{on} {when}.".replace("  ", " ")
    else:
        interpretation = (
            "Couldn't extract a filter from that question — showing the full "
            "log. Try naming a user and a time window, e.g. "
            "\"what did alice access last week?\""
        )

    if notes:
        interpretation += " " + " ".join(notes)
    if unparsed:
        interpretation += " Not understood (ignored): " + ", ".join(
            f"'{w}'" for w in unparsed
        ) + "."

    return ParsedQuery(
        query=query,
        interpretation=interpretation,
        matched=matched,
        parts=parts,
        unparsed=unparsed,
    )
