"""Audit query API.

Backs Demo 4 (the compliance-officer inquiry): filter the hash-chained
audit log by user, resource, query, decision, action, and time window,
and report the chain's verification status alongside the results.

Query is read-only and never mutates the chain. Results preserve chain
(append) order so a reviewer sees events as they happened.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from backend.audit.event_schema import AuditEvent
from backend.audit.hash_chain import HashChain, VerificationResult


@dataclass
class AuditQuery:
    """A read-only query filter over an audit chain.

    All criteria are optional and combined with AND. `resource_contains`
    matches a substring of the resource_id (e.g. "payment-gateway" for
    Demo 4). `since`/`until` bound the timestamp (inclusive).
    """

    user_id: str | None = None
    resource_id: str | None = None
    resource_contains: str | None = None
    query_id: str | None = None
    decision: str | None = None
    action: str | None = None
    since: datetime | None = None
    until: datetime | None = None

    def matches(self, event: AuditEvent) -> bool:
        """Return True iff the event satisfies every set criterion."""
        if self.user_id is not None and event.user_id != self.user_id:
            return False
        if self.resource_id is not None and event.resource_id != self.resource_id:
            return False
        if self.resource_contains is not None:
            rid = event.resource_id or ""
            if self.resource_contains not in rid:
                return False
        if self.query_id is not None and event.query_id != self.query_id:
            return False
        if self.decision is not None and event.decision != self.decision:
            return False
        if self.action is not None and event.action != self.action:
            return False
        if self.since is not None and event.timestamp < self.since:
            return False
        if self.until is not None and event.timestamp > self.until:
            return False
        return True


@dataclass
class AuditQueryResult:
    """Result of running an audit query.

    Attributes:
        events: Matching events in chain order.
        verification: Integrity status of the ENTIRE chain at query time.
    """

    events: list[AuditEvent] = field(default_factory=list)
    verification: VerificationResult | None = None

    @property
    def count(self) -> int:
        return len(self.events)

    @property
    def allow_count(self) -> int:
        return sum(1 for e in self.events if e.decision == "allow")

    @property
    def deny_count(self) -> int:
        return sum(1 for e in self.events if e.decision == "deny")


class AuditQueryEngine:
    """Runs read-only queries against a hash chain."""

    def __init__(self, chain: HashChain):
        self._chain = chain

    def run(self, query: AuditQuery) -> AuditQueryResult:
        """Filter the chain by the query and attach verification status."""
        matched = [e for e in self._chain.events() if query.matches(e)]
        return AuditQueryResult(
            events=matched,
            verification=self._chain.verify(),
        )

    def for_user(self, user_id: str) -> AuditQueryResult:
        """Convenience: all events for a user."""
        return self.run(AuditQuery(user_id=user_id))

    def for_resource_substring(self, substring: str) -> AuditQueryResult:
        """Convenience: all events whose resource_id contains a substring."""
        return self.run(AuditQuery(resource_contains=substring))
