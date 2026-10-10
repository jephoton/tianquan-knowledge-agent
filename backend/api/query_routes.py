"""Query routes — POST /query.

Runs a user's question through the orchestrator and returns the grounded
answer, citations, per-resource policy decisions (with reasons and ACL
versions for the policy inspector), and the audit chain head.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from backend.api.schemas import (
    CitationModel,
    DecisionModel,
    QueryRequest,
    QueryResponseModel,
)
from backend.auth.roles import can_audit, can_export
from backend.models import Action, DecisionResult
from backend.policy.policy_engine import PolicyEngine

router = APIRouter(tags=["query"])


@router.get("/resource/{resource_id:path}")
def get_resource_content(resource_id: str, request: Request, user_id: str):
    """Return a resource's content for the source-preview panel — but ONLY if
    the acting user is authorized to read it (re-checked against the live ACL).

    This is itself an access-control boundary: previewing a source the user
    cannot see would be a leak. A denied request returns 403 and is auditable
    via the normal pipeline (the preview is a read, same rules as a query).
    """
    state = request.app.state.tianquan
    user = state.identity.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail=f"unknown user: {user_id}")

    resource = None
    for connector in state.orchestrator._connectors:
        resource = connector.get_resource(resource_id)
        if resource is not None:
            break
    if resource is None:
        raise HTTPException(status_code=404, detail="resource not found")

    decision = PolicyEngine().decide(user, resource, Action.READ)
    if decision.result == DecisionResult.DENY:
        # No metadata leak: same opaque 403 regardless of why.
        raise HTTPException(status_code=403, detail="not authorized")

    return {
        "resource_id": resource.resource_id,
        "source": resource.source.value,
        "title": resource.title,
        "content": resource.content,
        "updated_at": resource.updated_at.isoformat() if resource.updated_at else None,
    }


@router.post("/query", response_model=QueryResponseModel)
def submit_query(req: QueryRequest, request: Request) -> QueryResponseModel:
    state = request.app.state.tianquan
    user = state.identity.get_user(req.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail=f"unknown user: {req.user_id}")

    resp = state.orchestrator.handle(user, req.question, k=req.k)

    # No-metadata-leak (INV7) at the wire boundary: a caller without audit
    # access never receives the DENY details — only the resources they could
    # see. The server does not send what the client is not allowed to know, so
    # denied resource IDs cannot leak into the browser DOM. Callers with
    # `audit_query` get the full decision list. Aggregate counts are safe
    # (they name no resource).
    auditor = can_audit(user.roles)
    exporter = can_export(user.roles)
    visible_decisions = [
        d for d in resp.decisions
        if auditor or d.result == DecisionResult.ALLOW
    ]

    return QueryResponseModel(
        query_id=resp.query_id,
        answer=resp.answer,
        no_access=resp.no_access,
        citations=[
            CitationModel(
                marker=c.marker, resource_id=c.resource_id,
                source=c.source, title=c.title,
                updated_at=c.updated_at.isoformat() if c.updated_at else None,
            )
            for c in resp.citations
        ],
        decisions=[
            DecisionModel(
                user_id=d.user_id,
                resource_id=d.resource_id,
                action=d.action.value,
                result=d.result.value,
                reason=d.reason,
                acl_version=d.acl_version,
                policy_version=d.policy_version,
            )
            for d in visible_decisions
        ],
        allow_count=resp.allow_count,
        deny_count=resp.deny_count,
        viewer_privileged=auditor,
        viewer_can_export=exporter,
        audit_chain_head=resp.audit_chain_head,
    )
