"""Audit routes — GET /audit, GET /audit/verify.

Backs the audit explorer (Demo 4). /audit filters the hash chain by user,
resource substring, query, decision, action; /audit/verify reports chain
integrity for the tamper-evidence demo.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from backend.api.schemas import AuditEventModel, AuditQueryResponseModel
from backend.audit.audit_query import AuditQuery


router = APIRouter(prefix="/audit", tags=["audit"])


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
) -> AuditQueryResponseModel:
    state = request.app.state.tianquan
    result = state.audit_query.run(
        AuditQuery(
            user_id=user_id,
            resource_contains=resource_contains,
            query_id=query_id,
            decision=decision,
            action=action,
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
    """Report whether the audit chain is intact (tamper-evidence)."""
    state = request.app.state.tianquan
    v = state.orchestrator.audit.verify()
    return {
        "valid": v.valid,
        "reason": v.reason,
        "broken_at_index": v.broken_at_index,
        "length": len(state.orchestrator.audit),
    }
