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

from backend.auth.roles import is_privileged
from backend.models import User

ACTING_USER_HEADER = "X-User-Id"


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


def require_privileged(
    request: Request,
    x_user_id: str | None = Header(default=None, alias=ACTING_USER_HEADER),
) -> User:
    """FastAPI dependency: 403 unless the acting user is privileged.

    Use on admin/audit routes. Returns the User when authorized.
    """
    user = resolve_user(request, x_user_id)
    if not is_privileged(user.roles):
        raise HTTPException(
            status_code=403,
            detail=(
                f"persona '{user.user_id}' ({', '.join(user.roles)}) lacks "
                "admin/audit access (requires manage_permissions or audit_query)"
            ),
        )
    return user
