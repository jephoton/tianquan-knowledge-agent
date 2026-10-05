"""Shared API dependencies — identity resolution and privilege gating.

The admin and audit surfaces are privileged: only personas whose role holds
`manage_permissions` (admin) or `audit_query` (compliance_officer) may use
them. Enforcement lives here, server-side — the frontend reflects it but does
not define it. A non-privileged caller gets 403, so hitting the endpoint
directly (bypassing the UI) is still refused.

The acting user is passed via the `X-User-Id` header (demo-grade identity;
a real deployment would use a signed session/token).
"""

from __future__ import annotations

from fastapi import Header, HTTPException, Request

from backend.auth.roles import has_permission
from backend.models import User

ACTING_USER_HEADER = "X-User-Id"

# Human-readable labels for permission-denied messages.
_PERM_LABELS = {
    "audit_query": "audit access",
    "manage_permissions": "permission management",
    "export": "export",
}


def resolve_user(request: Request, x_user_id: str | None) -> User:
    """Resolve the acting user from the X-User-Id header, or 401."""
    if not x_user_id:
        raise HTTPException(
            status_code=401,
            detail="missing X-User-Id header (no acting identity)",
        )
    user = request.app.state.tianquan.identity.get_user(x_user_id)
    if user is None:
        raise HTTPException(status_code=401, detail=f"unknown user: {x_user_id}")
    return user


def require_permission(permission: str):
    """Build a FastAPI dependency that 403s unless the caller holds `permission`.

    Enforcement is server-side: the frontend reflects it but does not define
    it, so hitting the endpoint directly (bypassing the UI) is still refused.
    """
    label = _PERM_LABELS.get(permission, permission)

    def _dep(
        request: Request,
        x_user_id: str | None = Header(default=None, alias=ACTING_USER_HEADER),
    ) -> User:
        user = resolve_user(request, x_user_id)
        if not has_permission(user.roles, permission):
            raise HTTPException(
                status_code=403,
                detail=(
                    f"persona '{user.user_id}' ({', '.join(user.roles)}) "
                    f"lacks {label} (requires '{permission}')"
                ),
            )
        return user

    return _dep
