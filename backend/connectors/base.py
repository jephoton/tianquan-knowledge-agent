"""Base connector interface for all source-system connectors."""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.models import ACL, Resource, User


class BaseConnector(ABC):
    """Abstract base class for source-system connectors.

    Each connector preserves its source-specific permission model.
    The unified Resource/ACL types are the common interface, but
    source_permissions inside ACL retains the native permission
    semantics (Confluence space/page, Jira project-role, etc.).
    """

    @abstractmethod
    def list_resources(self) -> list[Resource]:
        """Return all resources with current ACL info."""
        ...

    @abstractmethod
    def get_resource(self, resource_id: str) -> Resource | None:
        """Return a single resource with full content + current ACL."""
        ...

    @abstractmethod
    def get_acl(self, resource_id: str) -> ACL | None:
        """Return current ACL version and permission entries."""
        ...

    @abstractmethod
    def check_membership(self, user: User, resource_id: str) -> bool:
        """Source-native permission check for a user against a resource."""
        ...

    @abstractmethod
    def update_acl(
        self, resource_id: str, allowed_users: list[str] | None = None,
        allowed_roles: list[str] | None = None,
        denied_users: list[str] | None = None,
    ) -> ACL | None:
        """Update ACL for a resource, incrementing acl_version."""
        ...