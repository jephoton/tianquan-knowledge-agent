"""Tamper-evident audit trail for Tianquan.

- event_schema: canonical AuditEvent + deterministic serialization.
- hash_chain:   append-only SHA-256 hash chain with tamper detection.
- audit_query:  read-only query API over the chain (Demo 4).
"""

from backend.audit.event_schema import AuditEvent, event_from_decision
from backend.audit.hash_chain import HashChain, VerificationResult, GENESIS_HASH
from backend.audit.audit_query import (
    AuditQuery,
    AuditQueryEngine,
    AuditQueryResult,
)

__all__ = [
    "AuditEvent",
    "event_from_decision",
    "HashChain",
    "VerificationResult",
    "GENESIS_HASH",
    "AuditQuery",
    "AuditQueryEngine",
    "AuditQueryResult",
]
