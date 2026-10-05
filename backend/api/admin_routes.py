"""Admin routes — POST /admin/revoke, POST /admin/grant.

Live permission changes for Demo 3. A revoke/grant here mutates the live ACL
on the shared orchestrator's connectors, so the very next /query reflects it
with no reindex. The response reports the ACL version transition for the
policy inspector.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.api.deps import require_privileged
from backend.api.schemas import ACLChangeModel, RevokeGrantRequest
from backend.policy.admin import ResourceNotFound


# All admin routes require a privileged acting user (403 otherwise).
router = APIRouter(prefix="/admin", tags=["admin"],
                   dependencies=[Depends(require_privileged)])


def _apply(admin, action: str, req: RevokeGrantRequest):
    """Dispatch to the right admin method based on action + subject_kind."""
    if action == "revoke":
        if req.subject_kind == "user":
            return admin.revoke_user(req.resource_id, req.subject)
        return admin.revoke_role(req.resource_id, req.subject)
    # grant
    if req.subject_kind == "user":
        return admin.grant_user(req.resource_id, req.subject)
    return admin.grant_role(req.resource_id, req.subject)


def _to_model(change) -> ACLChangeModel:
    return ACLChangeModel(
        resource_id=change.resource_id,
        previous_version=change.previous_version,
        new_version=change.new_version,
        version_transition=change.version_transition,
        change=change.change,
        subject=change.subject,
        subject_kind=change.subject_kind,
    )


@router.post("/revoke", response_model=ACLChangeModel)
def revoke(req: RevokeGrantRequest, request: Request) -> ACLChangeModel:
    admin = request.app.state.tianquan.orchestrator.admin
    try:
        return _to_model(_apply(admin, "revoke", req))
    except ResourceNotFound:
        raise HTTPException(status_code=404, detail=f"unknown resource: {req.resource_id}")


@router.post("/grant", response_model=ACLChangeModel)
def grant(req: RevokeGrantRequest, request: Request) -> ACLChangeModel:
    admin = request.app.state.tianquan.orchestrator.admin
    try:
        return _to_model(_apply(admin, "grant", req))
    except ResourceNotFound:
        raise HTTPException(status_code=404, detail=f"unknown resource: {req.resource_id}")
