"""Tamper-evident hash-chained audit log.

Each event's hash is computed as:

    event_hash = SHA256(previous_hash + canonical_json(event))

where `previous_hash` is the prior event's hash (or GENESIS_HASH for the
first event). Because each event commits to the previous hash, altering
any past event — or reordering, inserting, or deleting one — changes that
event's hash and breaks every subsequent link. Verification recomputes the
chain and reports the first break.

This is the implementation-level realization of INV4 (EveryDecisionAudited):
the retrieval pipeline records every allow/deny decision here, and the chain
makes the record tamper-evident.

Storage is in-memory + optional JSON file persistence, which is sufficient
for the demo (ADR-0003 spirit: mock/simple where it isn't the differentiator).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass

from backend.audit.event_schema import (
    AuditEvent, event_from_decision, event_from_dict,
)
from backend.models import Decision

# The chain's anchor. The first event's previous_hash points here.
GENESIS_HASH = "0" * 64


def compute_hash(previous_hash: str, event: AuditEvent) -> str:
    """Compute the SHA-256 hash for an event given the previous hash."""
    material = (previous_hash + event.canonical_payload()).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


@dataclass
class VerificationResult:
    """Result of verifying chain integrity.

    Attributes:
        valid: True iff the entire chain verifies.
        broken_at_index: Index of the first event whose hash/link is invalid,
            or None if the chain is valid.
        reason: Human-readable explanation.
    """

    valid: bool
    broken_at_index: int | None = None
    reason: str = "chain_valid"


class HashChain:
    """An append-only, tamper-evident chain of audit events.

    If `persist_path` is set, the full chain is written to that JSON file on
    every append. That file is the on-disk source of truth: `verify_file()`
    re-reads and re-hashes it, so a hand-edit of the file (e.g. an insider
    flipping a DENY to ALLOW to cover their tracks) is detected.
    """

    def __init__(self, persist_path: str | None = None) -> None:
        self._events: list[AuditEvent] = []
        self._persist_path = persist_path

    # -- Append ---------------------------------------------------------

    def append(self, event: AuditEvent) -> AuditEvent:
        """Append an event, linking and hashing it. Returns the event.

        Mutates the event's `previous_hash` and `event_hash` to place it at
        the head of the chain, then persists the chain if configured.
        """
        event.previous_hash = self.head_hash()
        event.event_hash = compute_hash(event.previous_hash, event)
        self._events.append(event)
        if self._persist_path:
            self.save(self._persist_path)
        return event

    def append_decision(
        self, decision: Decision, query_id: str, detail: str = "",
        question: str = "", citations: list[dict[str, str]] | None = None,
    ) -> AuditEvent:
        """Convenience: build an AuditEvent from a Decision and append it.

        `detail` carries optional free text (e.g. the answer text captured on
        an answer event) into the tamper-evident record; `question` is the
        user's question for events produced by a query; `citations` is the
        answer's marker -> resource map.
        """
        event = event_from_decision(
            decision, query_id=query_id, event_id=str(uuid.uuid4()),
            detail=detail, question=question, citations=citations,
        )
        return self.append(event)

    def append_decisions(
        self, decisions: list[Decision], query_id: str, question: str = "",
    ) -> list[AuditEvent]:
        """Append many decisions under one query_id, preserving order."""
        return [
            self.append_decision(d, query_id, question=question)
            for d in decisions
        ]

    # -- Access ---------------------------------------------------------

    def head_hash(self) -> str:
        """Return the hash of the most recent event, or GENESIS_HASH."""
        return self._events[-1].event_hash if self._events else GENESIS_HASH

    def events(self) -> list[AuditEvent]:
        """Return all events in append order."""
        return list(self._events)

    def __len__(self) -> int:
        return len(self._events)

    # -- Verify ---------------------------------------------------------

    def verify(self) -> VerificationResult:
        """Recompute the chain and report the first break, if any.

        Detects: mutated event fields, broken previous_hash links,
        recomputed-hash mismatches, and (implicitly) reordering.
        """
        expected_prev = GENESIS_HASH
        for i, event in enumerate(self._events):
            if event.previous_hash != expected_prev:
                return VerificationResult(
                    valid=False,
                    broken_at_index=i,
                    reason=f"broken_link_at_{i}:previous_hash_mismatch",
                )
            recomputed = compute_hash(event.previous_hash, event)
            if recomputed != event.event_hash:
                return VerificationResult(
                    valid=False,
                    broken_at_index=i,
                    reason=f"tampered_event_at_{i}:hash_mismatch",
                )
            expected_prev = event.event_hash
        return VerificationResult(valid=True, reason="chain_valid")

    # -- Persistence ----------------------------------------------------

    def to_json(self) -> str:
        """Serialize the whole chain to JSON."""
        return json.dumps([e.to_dict() for e in self._events], indent=2)

    def save(self, path: str) -> None:
        """Persist the chain to a JSON file."""
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())

    @property
    def persist_path(self) -> str | None:
        return self._persist_path

    @staticmethod
    def verify_events(events: list[AuditEvent]) -> VerificationResult:
        """Verify an arbitrary list of events (used by both in-memory and
        file verification). Recomputes each hash and checks the links."""
        expected_prev = GENESIS_HASH
        for i, event in enumerate(events):
            if event.previous_hash != expected_prev:
                return VerificationResult(
                    valid=False, broken_at_index=i,
                    reason=f"broken_link_at_{i}:previous_hash_mismatch",
                )
            if compute_hash(event.previous_hash, event) != event.event_hash:
                return VerificationResult(
                    valid=False, broken_at_index=i,
                    reason=f"tampered_event_at_{i}:hash_mismatch",
                )
            expected_prev = event.event_hash
        return VerificationResult(valid=True, reason="chain_valid")

    def verify_file(self, path: str | None = None) -> VerificationResult:
        """Re-read the on-disk log and verify it from scratch.

        This is the realistic tamper check: it does NOT trust the in-memory
        chain. It parses the JSON file as written (or hand-edited) and
        recomputes the hashes over that content, so any out-of-band
        modification to the file is caught.
        """
        p = path or self._persist_path
        if not p:
            return VerificationResult(
                valid=False, reason="no_persist_path_configured")
        try:
            with open(p, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except FileNotFoundError:
            return VerificationResult(valid=False, reason="log_file_not_found")
        except json.JSONDecodeError as e:
            # A hand-edit that breaks JSON structure is itself tamper evidence.
            return VerificationResult(
                valid=False, broken_at_index=None,
                reason=f"log_file_corrupt_json:{e.msg}")
        events = [event_from_dict(d) for d in raw]
        return self.verify_events(events)
