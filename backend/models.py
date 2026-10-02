"""Core data models for Tianquan.

Defines the common Resource, User, Role, ACL, and Decision types
used across connectors, policy engine, retrieval, and audit layers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class Source(str, Enum):
    """Source platform identifiers."""

    CONFLUENCE = "confluence"
    JIRA = "jira"
    SLACK = "slack"
    GDRIVE = "gdrive"
    UPLOAD = "upload"


class SensitivityLevel(str, Enum):
    """Resource sensitivity classification."""

    PUBLIC = "public"
    INTERNAL = "internal"
    RESTRICTED = "restricted"
    CONFIDENTIAL = "confidential"


class Action(str, Enum):
    """Actions that can be requested on a resource."""

    READ = "read"
    CITE = "cite"
    EXPORT = "export"


class DecisionResult(str, Enum):
    """Outcome of a policy decision."""

    ALLOW = "allow"
    DENY = "deny"


@dataclass
class User:
    """A user identity in the system."""

    user_id: str
    name: str
    email: str
    roles: list[str] = field(default_factory=list)
    department: str = ""
    is_contractor: bool = False


@dataclass
class ACL:
    """Access control list for a resource.

    Attributes:
        acl_version: Monotonically increasing version, incremented on
            every permission change. Used for freshness checking.
        allowed_users: Explicit user IDs with access.
        allowed_roles: Role names that grant access.
        denied_users: Explicit user IDs denied access (overrides roles).
        source_permissions: Source-specific permission metadata, e.g.
            {"space": "ENG", "page_restriction": "editors"} for Confluence.
    """

    acl_version: int
    allowed_users: list[str] = field(default_factory=list)
    allowed_roles: list[str] = field(default_factory=list)
    denied_users: list[str] = field(default_factory=list)
    source_permissions: dict[str, Any] = field(default_factory=dict)


@dataclass
class Resource:
    """A knowledge resource from any source platform.

    This is the unified data model. Each connector translates its
    source-specific format into this common structure without
    flattening away permission semantics — source_permissions
    preserves the native permission model.
    """

    source: Source
    resource_id: str
    title: str
    content: str
    updated_at: datetime
    acl: ACL
    sensitivity_level: SensitivityLevel = SensitivityLevel.INTERNAL
    url: str = ""

    def is_authorized(self, user: User) -> bool:
        """Check if a user is authorized to read this resource.

        Deny list takes precedence over allow rules.
        """
        if user.user_id in self.acl.denied_users:
            return False
        if user.user_id in self.acl.allowed_users:
            return True
        if any(role in self.acl.allowed_roles for role in user.roles):
            return True
        return False


@dataclass
class Decision:
    """The result of a policy engine authorization check."""

    user_id: str
    resource_id: str
    action: Action
    result: DecisionResult
    reason: str
    acl_version: int
    policy_version: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def utc_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)