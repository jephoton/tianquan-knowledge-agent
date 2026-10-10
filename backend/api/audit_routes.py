"""Audit routes — GET /audit, GET /audit/verify.

Backs the audit explorer (Demo 4). /audit filters the hash chain by user,
resource substring, query, decision, action; /audit/verify reports chain
integrity for the tamper-evidence demo.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.api.deps import require_permission
from backend.api.schemas import AuditEventModel, AuditQueryResponseModel
from backend.audit.audit_query import AuditQuery


# All audit routes require audit_query (compliance_officer, security_team,
# admin; 403 otherwise).
router = APIRouter(prefix="/audit", tags=["audit"],
                   dependencies=[Depends(require_permission("audit_query"))])


def _event_model(event) -> AuditEventModel:
    d = event.to_dict()
    return AuditEventModel(**d)


@router.get("", response_model=AuditQueryResponseModel)
def query_audit(
    request: Request,
    user_id: str | None = None,
    resource_contains: str | None = None,
    query_id: str | None = None,
    decision: str | None = None,
    action: str | None = None,
    since: str | None = None,
    until: str | None = None,
) -> AuditQueryResponseModel:
    """Query the audit trail. `since`/`until` are ISO-8601 timestamps (or a
    plain date like 2026-10-01) bounding the event time — this is what lets a
    compliance officer ask 'what did alice access last week?'.
    """
    from datetime import datetime, timezone

    def _parse(ts: str | None):
        if not ts:
            return None
        try:
            dt = datetime.fromisoformat(ts)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"bad timestamp: {ts}")
        # Normalize naive timestamps to UTC so comparison with stored
        # (tz-aware) event timestamps works.
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    state = request.app.state.tianquan
    result = state.audit_query.run(
        AuditQuery(
            user_id=user_id,
            resource_contains=resource_contains,
            query_id=query_id,
            decision=decision,
            action=action,
            since=_parse(since),
            until=_parse(until),
        )
    )
    return AuditQueryResponseModel(
        count=result.count,
        allow_count=result.allow_count,
        deny_count=result.deny_count,
        chain_valid=result.verification.valid,
        chain_status=result.verification.reason,
        events=[_event_model(e) for e in result.events],
    )


@router.get("/verify")
def verify_chain(request: Request) -> dict:
    """Report whether the in-memory audit chain is intact (tamper-evidence)."""
    state = request.app.state.tianquan
    v = state.orchestrator.audit.verify()
    return {
        "valid": v.valid,
        "reason": v.reason,
        "broken_at_index": v.broken_at_index,
        "length": len(state.orchestrator.audit),
    }


@router.get("/verify-file")
def verify_file(request: Request) -> dict:
    """Re-read the on-disk audit log and verify it from scratch.

    Unlike /verify (in-memory), this parses the actual JSON log file and
    recomputes every hash over its current contents — so a hand-edit of the
    file (the realistic insider-tamper scenario) is detected. This is the
    endpoint behind the "verify log file" demo.
    """
    state = request.app.state.tianquan
    chain = state.orchestrator.audit
    v = chain.verify_file()
    return {
        "valid": v.valid,
        "reason": v.reason,
        "broken_at_index": v.broken_at_index,
        "path": chain.persist_path,
    }


@router.post("/tamper")
def tamper_chain(request: Request, index: int = 0, field: str = "resource_id") -> dict:
    """Tamper with an audit event to demonstrate chain breakage (Demo 6).

    Mutates a single field on the event at the given index. The next
    /audit/verify call will report CHAIN TAMPERED with the break index.
    """
    state = request.app.state.tianquan
    chain = state.orchestrator.audit
    events = chain.events()
    if not events:
        return {"error": "no events to tamper with"}
    idx = min(index, len(events) - 1)
    # Mutate the field — this changes the canonical payload, so the
    # recomputed hash will no longer match event_hash.
    setattr(events[idx], field, "TAMPERED_" + getattr(events[idx], field, ""))
    return {
        "tampered_index": idx,
        "field": field,
        "message": f"Event #{idx} field '{field}' modified. Verify chain to see the break.",
    }
