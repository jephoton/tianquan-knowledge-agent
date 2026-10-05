"""Export routes — POST /export.

Export is a distinct, higher-bar action than read: taking answer content OUT
of the audited environment. The caller must hold the `export` permission, and
each cited resource is RE-CHECKED with Action.EXPORT against its live ACL
before being released. Every export decision (allow and deny) is audited.

This models a second axis of access control beyond retrieval: a user may be
able to READ a blended answer in-session yet not EXPORT one of its sources.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from backend.api.deps import require_permission
from backend.models import User

# Exporting requires the `export` permission (403 otherwise).
router = APIRouter(prefix="/export", tags=["export"])


@router.post("")
def export_resources(
    request: Request,
    body: dict,
    user: User = Depends(require_permission("export")),
) -> dict:
    """Re-check EXPORT per cited resource for the acting user and audit it.

    Request body: {"resource_ids": [...]}. Returns which resources may be
    exported and which were denied (per-resource EXPORT re-evaluation).
    """
    resource_ids = body.get("resource_ids", [])
    orchestrator = request.app.state.tianquan.orchestrator
    result = orchestrator.export(user, resource_ids)
    return result
