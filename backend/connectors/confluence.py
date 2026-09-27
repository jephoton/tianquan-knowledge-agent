"""Mock Confluence connector.

Permission model: space-level + page-level restrictions.
- Spaces have base visibility (public, internal, restricted).
- Individual pages can override space defaults with named restrictions.
- source_permissions: {"space": "ENG", "page_restriction": "editors" | "named" | null}
"""

from __future__ import annotations

from datetime import datetime, timezone
from copy import deepcopy

from backend.connectors.base import BaseConnector
from backend.models import ACL, Resource, Source, SensitivityLevel, User


def _ts(year: int, month: int, day: int, hour: int = 12) -> datetime:
    return datetime(year, month, day, hour, tzinfo=timezone.utc)


def _seed_resources() -> dict[str, Resource]:
    """Return seed Confluence pages keyed by resource_id."""
    resources: dict[str, Resource] = {}

    def add(
        rid, title, content, updated, acl_version,
        allowed_users, allowed_roles,
        denied_users=None,
        sensitivity=SensitivityLevel.INTERNAL,
        space="", page_restriction=None, url="",
    ):
        resources[rid] = Resource(
            source=Source.CONFLUENCE,
            resource_id=rid,
            title=title,
            content=content,
            updated_at=updated,
            sensitivity_level=sensitivity,
            url=url or f"https://companya.atlassian.net/wiki/{rid}",
            acl=ACL(
                acl_version=acl_version,
                allowed_users=allowed_users,
                allowed_roles=allowed_roles,
                denied_users=denied_users or [],
                source_permissions={
                    "space": space,
                    "page_restriction": page_restriction,
                },
            ),
        )

    # Engineering space — internal, visible to all engineers
    add(
        "confluence:db-migration-plan",
        "Database Migration Project - Q3 Plan",
        (
            "# Database Migration Project\n\n"
            "## Objective\n"
            "Migrate the primary PostgreSQL cluster from v13 to v16 "
            "with zero downtime.\n\n"
            "## Timeline\n"
            "- Phase 1 (Week 1-2): Set up new cluster, configure "
            "logical replication.\n"
            "- Phase 2 (Week 3): Cut over read traffic. Monitor 48h.\n"
            "- Phase 3 (Week 4): Cut over write traffic. Decommission "
            "old cluster.\n\n"
            "## Risks\n"
            "- Replication lag during peak hours\n"
            "- Connection pool exhaustion during cutover\n"
            "- Rollback complexity if write cutover fails\n\n"
            "## Status\n"
            "Phase 2 complete. Read traffic on new cluster. Write "
            "cutover scheduled for Friday 2AM SGT."
        ),
        _ts(2026, 9, 20, 14),
        acl_version=1,
        allowed_users=[],
        allowed_roles=["engineer", "senior_engineer", "admin"],
        sensitivity=SensitivityLevel.INTERNAL,
        space="ENG",
    )

    # Engineering runbook — recently updated (for freshness demo)
    add(
        "confluence:payment-runbook",
        "Payment Service Incident Runbook",
        (
            "# Payment Service Incident Runbook\n\n"
            "## Last updated: 2026-09-27 13:00 SGT\n\n"
            "## Triage Steps\n"
            "1. Check Stripe webhook health dashboard.\n"
            "2. Verify payment-service pod health.\n"
            "3. Check Redis connectivity for idempotency keys.\n\n"
            "## Failover Procedure\n"
            "1. Switch payment-service to backup region.\n"
            "2. **NEW STEP (added 2026-09-27):** Enable circuit breaker "
            "on payment-gateway client with 50% threshold before failover "
            "to prevent cascade.\n"
            "3. Drain connections from primary region.\n"
            "4. Verify failover via health check endpoint.\n\n"
            "## Escalation\n"
            "- P0: Page on-call + VP Engineering\n"
            "- P1: Page on-call only"
        ),
        _ts(2026, 9, 27, 13),
        acl_version=2,
        allowed_users=[],
        allowed_roles=["engineer", "senior_engineer", "admin"],
        sensitivity=SensitivityLevel.INTERNAL,
        space="ENG",
    )

    # Security space — restricted to security team only (demo 2)
    add(
        "confluence:q3-breach-report",
        "Q3 Security Incident Report - Data Breach",
        (
            "# Q3 Security Incident Report\n\n"
            "## Classification: CONFIDENTIAL\n\n"
            "## Summary\n"
            "On 2026-08-15, an unauthorized actor gained access to the "
            "staging database via a leaked service account credential "
            "found in a public Slack channel.\n\n"
            "## Impact\n"
            "- ~2,000 staging customer records exposed.\n"
            "- Service account staging-deploy compromised.\n\n"
            "## Root Cause\n"
            "Credential committed to a public Slack channel by a "
            "contractor during deployment troubleshooting.\n\n"
            "## Remediation\n"
            "1. Rotated all staging service account credentials.\n"
            "2. Implemented secret scanning on Slack messages.\n"
            "3. Restricted CI/CD secret access to senior engineers."
        ),
        _ts(2026, 8, 20, 9),
        acl_version=1,
        allowed_users=["charlie"],
        allowed_roles=["security_team"],
        sensitivity=SensitivityLevel.CONFIDENTIAL,
        space="SEC",
        page_restriction="named",
    )

    # Finance space — restricted to finance team
    add(
        "confluence:q3-budget",
        "Q3 Budget Report - Finance",
        (
            "# Q3 Budget Report\n\n"
            "## Revenue\n"
            "- Q3 Revenue: $4.2M (up 12% QoQ)\n\n"
            "## Expenses\n"
            "- Engineering: $1.8M\n"
            "- Operations: $600K\n"
            "- Marketing: $400K\n\n"
            "## Runway\n"
            "Current runway: 18 months at current burn rate."
        ),
        _ts(2026, 9, 15, 10),
        acl_version=1,
        allowed_users=["erin"],
        allowed_roles=["finance_analyst", "admin"],
        sensitivity=SensitivityLevel.RESTRICTED,
        space="FIN",
        page_restriction="named",
    )

    # Public engineering decision doc (for auth service demo query)
    add(
        "confluence:auth-service-design",
        "New Auth Service - Design Decision",
        (
            "# Auth Service Design Decision\n\n"
            "## Decision\n"
            "Adopt a dedicated auth service using OAuth 2.1 with PKCE.\n\n"
            "## Rationale\n"
            "- Eliminates shared session secret across services.\n"
            "- Enables fine-grained scope-based access.\n"
            "- Supports eventual SSO integration.\n\n"
            "## Trade-offs\n"
            "- Adds one network hop for auth verification.\n"
            "- Requires token refresh logic in all clients."
        ),
        _ts(2026, 9, 10, 15),
        acl_version=1,
        allowed_users=[],
        allowed_roles=["engineer", "senior_engineer", "admin"],
        sensitivity=SensitivityLevel.INTERNAL,
        space="ENG",
    )

    return resources


class ConfluenceConnector(BaseConnector):
    """Mock Confluence connector with space/page-based permissions."""

    def __init__(self):
        self._resources = _seed_resources()

    def list_resources(self) -> list[Resource]:
        return list(self._resources.values())

    def get_resource(self, resource_id: str) -> Resource | None:
        return self._resources.get(resource_id)

    def get_acl(self, resource_id: str) -> ACL | None:
        res = self._resources.get(resource_id)
        return res.acl if res else None

    def check_membership(self, user: User, resource_id: str) -> bool:
        res = self._resources.get(resource_id)
        if not res:
            return False
        return res.is_authorized(user)

    def update_acl(
        self, resource_id: str, allowed_users=None,
        allowed_roles=None, denied_users=None,
    ) -> ACL | None:
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