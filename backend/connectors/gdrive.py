"""Mock Google Drive connector.

Permission model: file-folder-user sharing (view, comment, edit).
- Shared drives: visible to drive members.
- Personal drives: visible to explicit sharees.
- source_permissions: {"drive": "...", "share_type": "...", "path": "..."}
"""

from __future__ import annotations

from datetime import datetime, timezone
from copy import deepcopy

from backend.connectors.base import BaseConnector
from backend.models import ACL, Resource, Source, SensitivityLevel, User


def _ts(year, month, day, hour=12):
    return datetime(year, month, day, hour, tzinfo=timezone.utc)


def _seed_resources():
    resources = {}

    def add(rid, title, content, updated, acl_version,
            allowed_users, allowed_roles,
            denied_users=None, sensitivity=SensitivityLevel.INTERNAL,
            drive="", share_type="view", path=""):
        resources[rid] = Resource(
            source=Source.GDRIVE,
            resource_id=rid,
            title=title,
            content=content,
            updated_at=updated,
            sensitivity_level=sensitivity,
            url=f"https://drive.google.com/{path}",
            acl=ACL(
                acl_version=acl_version,
                allowed_users=allowed_users,
                allowed_roles=allowed_roles,
                denied_users=denied_users or [],
                source_permissions={
                    "drive": drive,
                    "share_type": share_type,
                    "path": path,
                },
            ),
        )

    add(
        "gdrive:payment-outage-postmortem",
        "Payment Outage Postmortem - 2026-09-14",
        "Postmortem: Payment Service Outage\n"
        "Date: 2026-09-14 | Duration: 45 min | Impact: All SG payments\n\n"
        "Summary:\n"
        "Redis primary failed, triggering failover to replica. "
        "Circuit breaker was disabled (erroneous deploy 2026-09-10), "
        "so failure cascaded to all payment-service pods.\n\n"
        "Timeline:\n"
        "03:12 Redis failover | 03:25 On-call paged\n"
        "03:45 Failover to backup | 03:57 Full recovery\n\n"
        "Action Items:\n"
        "1. Re-enable circuit breaker (PAY-460) - DONE\n"
        "2. Circuit breaker validation in CI (PAY-461)\n"
        "3. Redis failover chaos test",
        _ts(2026, 9, 17, 14), 1,
        ["alice", "jdoe"],
        ["engineer", "senior_engineer", "admin"],
        drive="shared:engineering",
        path="postmortems/payment-outage-2026-09-14.pdf",
    )

    add(
        "gdrive:arch-diagram-v2",
        "System Architecture Diagram v2",
        "System architecture document.\n"
        "Diagrams: service topology, data flow, trust boundaries,\n"
        "network segmentation. Last updated: 2026-09-15",
        _ts(2026, 9, 15, 10), 1,
        ["alice", "jdoe"],
        ["engineer", "senior_engineer", "admin"],
        drive="shared:engineering",
        path="architecture/arch-diagram-v2.pdf",
    )

    add(
        "gdrive:q3-budget-export",
        "Q3 Budget Export - Finance",
        "Q3 Budget Export\n"
        "Revenue: $4.2M | Expenses: $2.8M | Net: $1.4M\n"
        "Runway: 18 months.",
        _ts(2026, 9, 16, 9), 1,
        ["erin"],
        ["finance_analyst", "admin"],
        sensitivity=SensitivityLevel.RESTRICTED,
        drive="shared:finance",
        path="budgets/q3-budget-export.xlsx",
    )

    add(
        "gdrive:onboarding-guide",
        "New Employee Onboarding Guide",
        "Welcome to Company A!\n\n"
        "1. Set up laptop with IT script.\n"
        "2. Request Confluence, Jira, Slack access.\n"
        "3. Clone repo, run make dev.\n"
        "4. Read ENG handbook in Confluence.\n\n"
        "Questions? Ask in #help-desk.",
        _ts(2026, 9, 1, 10), 1,
        [],
        ["contractor", "engineer", "senior_engineer",
         "finance_analyst", "security_team",
         "compliance_officer", "admin"],
        sensitivity=SensitivityLevel.PUBLIC,
        drive="shared:hr",
        path="onboarding/new-employee-guide.pdf",
    )

    return resources


class GDriveConnector(BaseConnector):
    """Mock Google Drive connector with file-folder-user sharing."""

    def __init__(self):
        self._resources = _seed_resources()

    def list_resources(self):
        return list(self._resources.values())

    def get_resource(self, resource_id):
        return self._resources.get(resource_id)

    def get_acl(self, resource_id):
        res = self._resources.get(resource_id)
        return res.acl if res else None

    def check_membership(self, user, resource_id):
        res = self._resources.get(resource_id)
        if not res:
            return False
        return res.is_authorized(user)

    def update_acl(self, resource_id, allowed_users=None,
                   allowed_roles=None, denied_users=None):
        res = self._resources.get(resource_id)
        if not res:
            return None
        if allowed_users is not None:
            res.acl.allowed_users = allowed_users
        if allowed_roles is not None:
            res.acl.allowed_roles = allowed_roles
        if denied_users is not None:
            res.acl.denied_users = denied_users
        res.acl.acl_version += 1
        return deepcopy(res.acl)