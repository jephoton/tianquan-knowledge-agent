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

router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResponseModel)
def submit_query(req: QueryRequest, request: Request) -> QueryResponseModel:
    state = request.app.state.veribrain
    user = state.identity.get_user(req.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail=f"unknown user: {req.user_id}")

    resp = state.orchestrator.handle(user, req.question, k=req.k)

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
            for d in resp.decisions
        ],
        allow_count=resp.allow_count,
        deny_count=resp.deny_count,
        audit_chain_head=resp.audit_chain_head,
    )
