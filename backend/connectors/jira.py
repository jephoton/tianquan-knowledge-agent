"""Mock Jira connector.

Permission model: project-role + issue-level security.
- Projects have role-based visibility (developer, qa, admin).
- Individual issues can have security levels that restrict visibility
  to specific roles (e.g., security-sensitive bugs only visible to
  the security team).
- source_permissions: {"project": "MIG", "issue_security": "security" | null}
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
            project="", issue_security=None, url=""):
        resources[rid] = Resource(
            source=Source.JIRA,
            resource_id=rid,
            title=title,
            content=content,
            updated_at=updated,
            sensitivity_level=sensitivity,
            url=url or f"https://companya.atlassian.net/browse/{rid}",
            acl=ACL(
                acl_version=acl_version,
                allowed_users=allowed_users,
                allowed_roles=allowed_roles,
                denied_users=denied_users or [],
                source_permissions={
                    "project": project,
                    "issue_security": issue_security,
                },
            ),
        )

    add(
        "MIG-231",
        "[MIG-231] DB Migration: Write traffic cutover pending",
        "Issue: MIG-231 | Project: Database Migration (MIG)\n"
        "Type: Task | Status: In Progress | Assignee: Alice Chen\n\n"
        "Phase 2 (read cutover) is complete. Phase 3 (write cutover) "
        "is scheduled for Friday 2AM SGT.\n\n"
        "Blockers:\n"
        "- Need to verify replication lag is under 100ms during peak.\n"
        "- Connection pool sizing for new cluster needs review.\n\n"
        "Comments:\n"
        "- jdoe: Replication lag averaging 40ms, should be fine.\n"
        "- alice: Pool sizing looks good, tested with 2x load.",
        _ts(2026, 9, 25, 16), 1,
        ["alice", "jdoe"],
        ["engineer", "senior_engineer", "admin"],
        project="MIG",
    )

    add(
        "MIG-232",
        "[MIG-232] DB Migration: Verify replication lag under peak load",
        "Issue: MIG-232 | Project: Database Migration (MIG)\n"
        "Type: Sub-task | Status: Done | Assignee: John Doe\n\n"
        "Verified replication lag under simulated peak load (2x normal).\n"
        "Average lag: 40ms, max: 85ms. Within 100ms threshold.\n\n"
        "Acceptance criteria met. Story points: 2.",
        _ts(2026, 9, 24, 10), 1,
        ["alice", "jdoe"],
        ["engineer", "senior_engineer", "admin"],
        project="MIG",
    )

    add(
        "PAY-456",
        "[PAY-456] Payment outage - 2026-09-14 root cause analysis",
        "Issue: PAY-456 | Project: Payment Service (PAY)\n"
        "Type: Bug | Status: Closed | Priority: P0\n\n"
        "On 2026-09-14, the payment service experienced a 45-minute "
        "outage affecting all Singapore transactions.\n\n"
        "Root Cause:\n"
        "Cascading failure triggered by Redis failover. The circuit "
        "breaker on the payment-gateway client was disabled during a "
        "previous deployment, allowing the failure to cascade.\n\n"
        "Follow-up:\n"
        "- Created PAY-460: Re-enable circuit breaker.\n"
        "- Created PAY-461: Add circuit breaker config validation to CI.",
        _ts(2026, 9, 16, 11), 1,
        ["alice", "jdoe"],
        ["engineer", "senior_engineer", "admin"],
        project="PAY",
    )

    add(
        "PAY-460",
        "[PAY-460] Re-enable circuit breaker on payment-gateway client",
        "Issue: PAY-460 | Project: Payment Service (PAY)\n"
        "Type: Task | Status: Done\n\n"
        "Re-enabled circuit breaker with 50% error threshold. "
        "Added integration test to verify breaker state on deploy.",
        _ts(2026, 9, 18, 14), 1,
        ["alice", "jdoe"],
        ["engineer", "senior_engineer", "admin"],
        project="PAY",
    )

    add(
        "SEC-101",
        "[SEC-101] Security: Leaked credential in staging deployment",
        "Issue: SEC-101 | Project: Security (SEC)\n"
        "Type: Security Issue | Status: Closed\n"
        "Issue Security Level: security\n\n"
        "Service account credential 'staging-deploy' was found "
        "committed in a public Slack channel. Credential rotated, "
        "access logs reviewed, no unauthorized production access detected.",
        _ts(2026, 8, 16, 8), 1,
        ["charlie"],
        ["security_team"],
        sensitivity=SensitivityLevel.CONFIDENTIAL,
        project="SEC",
        issue_security="security",
    )

    add(
        "HELP-12",
        "[HELP-12] FAQ: How to request access to a Confluence space",
        "Issue: HELP-12 | Project: Help Desk (HELP)\n"
        "Type: Documentation | Status: Done\n\n"
        "To request access to a Confluence space:\n"
        "1. Navigate to the space.\n"
        "2. Click 'Space Settings' > 'Permissions'.\n"
        "3. Click 'Request Access'.",
        _ts(2026, 9, 5, 10), 1,
        [],
        ["contractor", "engineer", "senior_engineer",
         "finance_analyst", "security_team",
         "compliance_officer", "admin"],
        sensitivity=SensitivityLevel.PUBLIC,
        project="HELP",
    )

    return resources


class JiraConnector(BaseConnector):
    """Mock Jira connector with project-role + issue-security permissions."""

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