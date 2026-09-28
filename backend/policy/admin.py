"""Permission administration — live grant / revoke.

Exposes revocation and grant as first-class admin actions on top of the
connectors' `update_acl` (which bumps `acl_version` on every change). This is
what makes Demo 3 tangible: an admin revokes access, and the very next query
excludes the content — no reindex, no stale-permitted data served.

The enforcement itself is not implemented here. It already lives in the
retrieval pipeline: the permission filter re-fetches the live ACL per candidate
(M3) and the freshness checker flags stale snapshots (M2). This service simply
mutates the live ACL and reports the version transition so the UI / demo can
show "ACL v17 -> v18, DENY due to revoked membership".
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.connectors.base import BaseConnector
from backend.models import ACL


@dataclass
class ACLChange:
    """The result of a grant/revoke, capturing the version transition.

    Attributes:
        resource_id: The affected resource.
        previous_version: acl_version before the change.
        new_version: acl_version after the change (previous + 1).
        change: "revoke" or "grant".
        subject: The user_id or role affected.
        subject_kind: "user" or "role".
    """

    resource_id: str
    previous_version: int
    new_version: int
    change: str
    subject: str
    subject_kind: str

    @property
    def version_transition(self) -> str:
        """Human-readable transition, e.g. 'v17 -> v18' (for the demo UI)."""
        return f"v{self.previous_version} -> v{self.new_version}"


class ResourceNotFound(Exception):
    """Raised when no registered connector owns the resource."""


class PermissionAdmin:
    """Admin service for live permission changes across connectors."""

    def __init__(self, connectors: list[BaseConnector]):
        self._connectors = list(connectors)

    def _owning_connector(self, resource_id: str) -> BaseConnector:
        """Return the connector that owns a resource, or raise."""
        for connector in self._connectors:
            if connector.get_acl(resource_id) is not None:
                return connector
        raise ResourceNotFound(resource_id)

    def _current_acl(self, resource_id: str) -> ACL:
        acl = self._owning_connector(resource_id).get_acl(resource_id)
        if acl is None:  # pragma: no cover - guarded by _owning_connector
            raise ResourceNotFound(resource_id)
        return acl

    # -- Revoke ---------------------------------------------------------

    def revoke_user(self, resource_id: str, user_id: str) -> ACLChange:
        """Revoke a user's access to a resource.

        Removes the user from `allowed_users` and adds them to `denied_users`
        (deny takes precedence, so this is definitive even if a role would
        otherwise grant access). Bumps acl_version.
        """
        connector = self._owning_connector(resource_id)
        acl = self._current_acl(resource_id)
        prev = acl.acl_version

        new_allowed = [u for u in acl.allowed_users if u != user_id]
        new_denied = list(acl.denied_users)
        if user_id not in new_denied:
            new_denied.append(user_id)

        connector.update_acl(
            resource_id,
            allowed_users=new_allowed,
            denied_users=new_denied,
        )
        return ACLChange(
            resource_id=resource_id,
            previous_version=prev,
            new_version=self._current_acl(resource_id).acl_version,
            change="revoke",
            subject=user_id,
            subject_kind="user",
        )

    def revoke_role(self, resource_id: str, role: str) -> ACLChange:
        """Revoke a role's access to a resource (removes it from allowed_roles)."""
        connector = self._owning_connector(resource_id)
        acl = self._current_acl(resource_id)
        prev = acl.acl_version

        new_roles = [r for r in acl.allowed_roles if r != role]
        connector.update_acl(resource_id, allowed_roles=new_roles)
        return ACLChange(
            resource_id=resource_id,
            previous_version=prev,
            new_version=self._current_acl(resource_id).acl_version,
            change="revoke",
            subject=role,
            subject_kind="role",
        )

    # -- Grant ----------------------------------------------------------

    def grant_user(self, resource_id: str, user_id: str) -> ACLChange:
        """Grant a user access (adds to allowed_users, clears any deny)."""
        connector = self._owning_connector(resource_id)
        acl = self._current_acl(resource_id)
        prev = acl.acl_version

        new_allowed = list(acl.allowed_users)
        if user_id not in new_allowed:
            new_allowed.append(user_id)
        new_denied = [u for u in acl.denied_users if u != user_id]

        connector.update_acl(
            resource_id,
            allowed_users=new_allowed,
            denied_users=new_denied,
        )
        return ACLChange(
            resource_id=resource_id,
            previous_version=prev,
            new_version=self._current_acl(resource_id).acl_version,
            change="grant",
            subject=user_id,
            subject_kind="user",
        )

    def grant_role(self, resource_id: str, role: str) -> ACLChange:
        """Grant a role access (adds it to allowed_roles)."""
        connector = self._owning_connector(resource_id)
        acl = self._current_acl(resource_id)
        prev = acl.acl_version

        new_roles = list(acl.allowed_roles)
        if role not in new_roles:
            new_roles.append(role)
        connector.update_acl(resource_id, allowed_roles=new_roles)
        return ACLChange(
            resource_id=resource_id,
            previous_version=prev,
            new_version=self._current_acl(resource_id).acl_version,
            change="grant",
            subject=role,
            subject_kind="role",
        )
