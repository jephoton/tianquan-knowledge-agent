"""Canonical audit event schema.

An AuditEvent is the tamper-evident record of a single authorization
decision (or answer emission). Events are linked into a hash chain
(see hash_chain.py) so that any modification to a past event is
detectable.

The canonical JSON serialization is deterministic: keys sorted, no
insignificant whitespace, timestamps as ISO-8601 UTC. This determinism
is essential — the hash is computed over the canonical form, so two
parties computing the hash of the same logical event must agree byte
for byte.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from backend.models import Action, Decision, DecisionResult


def utc_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


# The fields that constitute the canonical, hashed payload of an event.
# `event_hash` is intentionally NOT part of the payload (it is the output),
# and `previous_hash` IS part of the payload (it chains to the prior event).
_PAYLOAD_FIELDS = (
    "event_id",
    "timestamp",
    "user_id",
    "query_id",
    "resource_id",
    "action",
    "decision",
    "reason",
    "acl_version",
    "policy_version",
    "previous_hash",
)


@dataclass
class AuditEvent:
    """A single tamper-evident audit record.

    Attributes mirror architecture.md §4. `event_hash` is filled in by the
    hash chain when the event is appended; `previous_hash` links to the
    prior event's hash (or the genesis constant for the first event).
    """

    event_id: str
    user_id: str
    query_id: str
    action: str
    decision: str
    reason: str
    acl_version: int
    policy_version: int
    resource_id: str | None = None
    timestamp: datetime = field(default_factory=utc_now)
    previous_hash: str = ""
    event_hash: str = ""

    def canonical_payload(self) -> str:
        """Return the deterministic JSON string that gets hashed.

        Excludes `event_hash` (the output) but includes `previous_hash`
        (the chain link). Keys are sorted; timestamp is ISO-8601 UTC.
        """
        payload: dict[str, Any] = {}
        for name in _PAYLOAD_FIELDS:
            value = getattr(self, name)
            if isinstance(value, datetime):
                value = value.astimezone(timezone.utc).isoformat()
            payload[name] = value
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    def to_dict(self) -> dict[str, Any]:
        """Full serialization including the event_hash, for storage/query."""
        d: dict[str, Any] = {}
        for name in _PAYLOAD_FIELDS:
            value = getattr(self, name)
            if isinstance(value, datetime):
                value = value.astimezone(timezone.utc).isoformat()
            d[name] = value
        d["event_hash"] = self.event_hash
        return d


def event_from_decision(
    decision: Decision,
    query_id: str,
    event_id: str,
) -> AuditEvent:
    """Build an (unchained) AuditEvent from a policy Decision.

    The returned event has no previous_hash/event_hash yet — those are
    assigned when it is appended to the hash chain.
    """
    action = decision.action.value if isinstance(decision.action, Action) else str(decision.action)
    result = (
        decision.result.value
        if isinstance(decision.result, DecisionResult)
        else str(decision.result)
    )
    return AuditEvent(
        event_id=event_id,
        user_id=decision.user_id,
        query_id=query_id,
        resource_id=decision.resource_id,
        action=action,
        decision=result,
        reason=decision.reason,
        acl_version=decision.acl_version,
        policy_version=decision.policy_version,
        timestamp=decision.timestamp,
    )
