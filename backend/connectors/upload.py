"""Upload connector for real-time document ingestion (Demo 7).

Allows an admin to upload raw text/JSON files at runtime. Each uploaded
document becomes a first-class Resource in the index, with its own ACL
defaulting to internal visibility (all roles read, no contractors).

This demonstrates the "real-time data ingestion" the organiser asked
about — instead of hardcoded mock data, the system ingests documents
on the fly and they appear in query results immediately after reindex.
"""

from __future__ import annotations

from datetime import datetime, timezone
from copy import deepcopy

from backend.connectors.base import BaseConnector
from backend.models import (
    ACL,
    Resource,
    SensitivityLevel,
    Source,
    User,
)


class UploadConnector(BaseConnector):
    """In-memory connector for admin-uploaded documents.

    Documents are stored as resources with source=UPLOAD (a synthetic
    source that doesn't map to a real SaaS tool). ACLs default to
    internal: all roles can read, contractors are denied.

    The admin can override per-document after upload via the revoke/grant
    admin API, exactly as with any other connector.
    """

    def __init__(self) -> None:
        self._resources: dict[str, Resource] = {}

    def _default_acl(self) -> ACL:
        return ACL(
            acl_version=1,
            allowed_users=[],
            allowed_roles=[
                "admin",
                "engineer",
                "senior_engineer",
                "security_team",
                "compliance_officer",
            ],
            denied_users=[],
            source_permissions={"source": "upload"},
        )

    def add_document(
        self,
        resource_id: str,
        title: str,
        content: str,
        allowed_roles: list[str] | None = None,
        denied_users: list[str] | None = None,
    ) -> Resource:
        """Add or replace a document. Returns the created Resource."""
        acl = self._default_acl()
        if allowed_roles is not None:
            acl.allowed_roles = allowed_roles
        if denied_users is not None:
            acl.denied_users = denied_users

        resource = Resource(
            resource_id=resource_id,
            source=Source.UPLOAD,
            title=title,
            content=content,
            url=f"upload://{resource_id}",
            updated_at=datetime.now(timezone.utc),
            sensitivity_level=SensitivityLevel.INTERNAL,
            acl=acl,
        )
        self._resources[resource_id] = resource
        return resource

    def list_resources(self) -> list[Resource]:
        return [deepcopy(r) for r in self._resources.values()]

    def get_resource(self, resource_id: str) -> Resource | None:
        r = self._resources.get(resource_id)
        return deepcopy(r) if r else None

    def get_acl(self, resource_id: str) -> ACL | None:
        r = self._resources.get(resource_id)
        return deepcopy(r.acl) if r else None

    def check_membership(self, user: User, resource_id: str) -> bool:
        r = self._resources.get(resource_id)
        if not r:
            return False
        acl = r.acl
        if user.user_id in acl.denied_users:
            return False
        if user.user_id in acl.allowed_users:
            return True
        return bool(set(user.roles) & set(acl.allowed_roles))

    def update_acl(
        self,
        resource_id: str,
        allowed_users: list[str] | None = None,
        allowed_roles: list[str] | None = None,
        denied_users: list[str] | None = None,
    ) -> ACL | None:
        r = self._resources.get(resource_id)
        if not r:
            return None
        new_acl = deepcopy(r.acl)
        new_acl.acl_version += 1
        if allowed_users is not None:
            new_acl.allowed_users = allowed_users
        if allowed_roles is not None:
            new_acl.allowed_roles = allowed_roles
        if denied_users is not None:
            new_acl.denied_users = denied_users
        r.acl = new_acl
        return deepcopy(new_acl)
