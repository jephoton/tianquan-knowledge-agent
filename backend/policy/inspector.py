"""Permissions inspector — read-only "who can access what" lookups.

Answers the three questions a compliance officer or admin actually asks:

- **by user**   → which resources can this user read / export, and why
                  (via a direct user grant or via one of their roles)?
- **by role**   → which users hold this role, and which resources does it
                  grant access to?
- **by resource** → which users and roles can access this resource?

Access is computed by evaluating the *real* :class:`PolicyEngine` over the
live resources — not by reading raw ACL membership — so the answer reflects
the actual fail-closed decision logic (deny-lists, source-specific rules,
sensitivity clearance, action permissions). What the inspector shows is
exactly what a query would be allowed to retrieve.

Everything here is read-only; it never mutates an ACL.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.connectors.base import BaseConnector
from backend.models import Action, DecisionResult, Resource, User
from backend.policy.policy_engine import PolicyEngine


@dataclass
class ResourceAccess:
    """How a user can access one resource."""

    resource_id: str
    source: str
    title: str
    can_read: bool
    can_export: bool
    via: str  # "user-grant" | "role:<name>" | "denied" | "no-match"
    reason: str


@dataclass
class UserAccessReport:
    user_id: str
    name: str
    roles: list[str] = field(default_factory=list)
    resources: list[ResourceAccess] = field(default_factory=list)

    @property
    def readable_count(self) -> int:
        return sum(1 for r in self.resources if r.can_read)


@dataclass
class RoleReport:
    role: str
    members: list[str] = field(default_factory=list)   # user_ids holding the role
    resources: list[str] = field(default_factory=list)  # resource_ids the role grants


@dataclass
class ResourceReport:
    resource_id: str
    source: str
    title: str
    acl_version: int
    allowed_users: list[str] = field(default_factory=list)
    allowed_roles: list[str] = field(default_factory=list)
    denied_users: list[str] = field(default_factory=list)
    # Users who can actually read it per the PolicyEngine (effective access).
    effective_readers: list[str] = field(default_factory=list)


class PermissionsInspector:
    """Read-only permission lookups over the live connectors."""

    def __init__(self, connectors: list[BaseConnector], users: dict[str, User]):
        self._connectors = list(connectors)
        self._users = dict(users)
        self._engine = PolicyEngine()

    def _all_resources(self) -> list[Resource]:
        out: list[Resource] = []
        for c in self._connectors:
            out.extend(c.list_resources())
        return out

    # -- by user --------------------------------------------------------

    def for_user(self, user: User) -> UserAccessReport:
        """What can this user read / export, and via what grant?"""
        report = UserAccessReport(
            user_id=user.user_id, name=user.name, roles=list(user.roles),
        )
        for r in self._all_resources():
            read = self._engine.decide(user, r, Action.READ)
            exp = self._engine.decide(user, r, Action.EXPORT)
            can_read = read.result == DecisionResult.ALLOW
            can_export = exp.result == DecisionResult.ALLOW

            # Explain *how* access is granted (or why not).
            if user.user_id in r.acl.denied_users:
                via = "denied"
            elif user.user_id in r.acl.allowed_users:
                via = "user-grant"
            else:
                via = "no-match"
                for role in user.roles:
                    if role in r.acl.allowed_roles:
                        via = f"role:{role}"
                        break

            report.resources.append(ResourceAccess(
                resource_id=r.resource_id,
                source=r.source.value,
                title=r.title,
                can_read=can_read,
                can_export=can_export,
                via=via,
                reason=read.reason,
            ))
        # Readable first, then by source/id for a stable, readable order.
        report.resources.sort(key=lambda a: (not a.can_read, a.source, a.resource_id))
        return report

    # -- by role --------------------------------------------------------

    def for_role(self, role: str) -> RoleReport:
        """Which users hold this role, and which resources does it grant?"""
        members = [uid for uid, u in self._users.items() if role in u.roles]
        resources = [
            r.resource_id for r in self._all_resources()
            if role in r.acl.allowed_roles
        ]
        return RoleReport(role=role, members=sorted(members), resources=sorted(resources))

    # -- by resource ----------------------------------------------------

    def for_resource(self, resource_id: str) -> ResourceReport | None:
        """Who can access this resource (raw ACL + effective readers)?"""
        resource: Resource | None = None
        for c in self._connectors:
            resource = c.get_resource(resource_id)
            if resource is not None:
                break
        if resource is None:
            return None

        effective = [
            uid for uid, u in self._users.items()
            if self._engine.decide(u, resource, Action.READ).result == DecisionResult.ALLOW
        ]
        acl = resource.acl
        return ResourceReport(
            resource_id=resource.resource_id,
            source=resource.source.value,
            title=resource.title,
            acl_version=acl.acl_version,
            allowed_users=list(acl.allowed_users),
            allowed_roles=list(acl.allowed_roles),
            denied_users=list(acl.denied_users),
            effective_readers=sorted(effective),
        )
