"""Admin routes — POST /admin/revoke, POST /admin/grant.

Live permission changes for Demo 3. A revoke/grant here mutates the live ACL
on the shared orchestrator's connectors, so the very next /query reflects it
with no reindex. The response reports the ACL version transition for the
policy inspector.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.api.deps import require_permission
from backend.api.schemas import (
    ACLChangeModel,
    ResourceReportModel,
    RevokeGrantRequest,
    RoleReportModel,
    UserAccessReportModel,
)
from backend.models import User
from backend.policy.admin import ResourceNotFound
from backend.policy.inspector import PermissionsInspector


# Revoke/grant require manage_permissions (admin only; 403 otherwise).
router = APIRouter(prefix="/admin", tags=["admin"],
                   dependencies=[Depends(require_permission("manage_permissions"))])


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


def _change(request: Request, actor: User, action: str, req: RevokeGrantRequest):
    """Apply a revoke/grant and record it in the audit trail."""
    orchestrator = request.app.state.tianquan.orchestrator
    try:
        change = _apply(orchestrator.admin, action, req)
    except ResourceNotFound:
        raise HTTPException(status_code=404, detail=f"unknown resource: {req.resource_id}")
    orchestrator.record_acl_change(actor, change)
    return _to_model(change)


@router.post("/revoke", response_model=ACLChangeModel)
def revoke(
    req: RevokeGrantRequest, request: Request,
    actor: User = Depends(require_permission("manage_permissions")),
) -> ACLChangeModel:
    return _change(request, actor, "revoke", req)


@router.post("/grant", response_model=ACLChangeModel)
def grant(
    req: RevokeGrantRequest, request: Request,
    actor: User = Depends(require_permission("manage_permissions")),
) -> ACLChangeModel:
    return _change(request, actor, "grant", req)


# -- permissions inspector (read-only "who can access what") -----------

def _inspector(request: Request) -> PermissionsInspector:
    state = request.app.state.tianquan
    connectors = state.orchestrator.admin._connectors
    return PermissionsInspector(connectors, state.identity.all_users())


@router.get("/permissions/resources")
def list_all_resources(request: Request) -> dict:
    """List every resource id/title/source (to populate the inspector picker)."""
    connectors = request.app.state.tianquan.orchestrator.admin._connectors
    items = []
    for c in connectors:
        for r in c.list_resources():
            items.append({
                "resource_id": r.resource_id,
                "title": r.title,
                "source": r.source.value,
            })
    items.sort(key=lambda x: (x["source"], x["resource_id"]))
    return {"count": len(items), "resources": items}


@router.get("/permissions/user/{user_id}", response_model=UserAccessReportModel)
def permissions_for_user(user_id: str, request: Request) -> UserAccessReportModel:
    """Which resources this user can read/export, and via which grant."""
    state = request.app.state.tianquan
    user = state.identity.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail=f"unknown user: {user_id}")
    rep = _inspector(request).for_user(user)
    return UserAccessReportModel(
        user_id=rep.user_id,
        name=rep.name,
        roles=rep.roles,
        readable_count=rep.readable_count,
        resources=[r.__dict__ for r in rep.resources],
    )


@router.get("/permissions/role/{role}", response_model=RoleReportModel)
def permissions_for_role(role: str, request: Request) -> RoleReportModel:
    """Which users hold this role and which resources it grants."""
    rep = _inspector(request).for_role(role)
    return RoleReportModel(role=rep.role, members=rep.members, resources=rep.resources)


@router.get("/permissions/resource/{resource_id:path}", response_model=ResourceReportModel)
def permissions_for_resource(resource_id: str, request: Request) -> ResourceReportModel:
    """Who can access this resource (raw ACL + effective readers)."""
    rep = _inspector(request).for_resource(resource_id)
    if rep is None:
        raise HTTPException(status_code=404, detail=f"unknown resource: {resource_id}")
    return ResourceReportModel(**rep.__dict__)
