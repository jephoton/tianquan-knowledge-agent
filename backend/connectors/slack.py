"""Mock Slack connector.

Permission model: channel membership (public, private, DM).
- Public channels: visible to all workspace members.
- Private channels: visible only to explicit members.
- DMs: visible only to participants.
- source_permissions: {"channel": "...", "channel_type": "...", "thread_ts": "..."}
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
            channel="", channel_type="public", thread_ts=""):
        resources[rid] = Resource(
            source=Source.SLACK,
            resource_id=rid,
            title=title,
            content=content,
            updated_at=updated,
            sensitivity_level=sensitivity,
            url=f"https://companya.slack.com/archives/{channel}",
            acl=ACL(
                acl_version=acl_version,
                allowed_users=allowed_users,
                allowed_roles=allowed_roles,
                denied_users=denied_users or [],
                source_permissions={
                    "channel": channel,
                    "channel_type": channel_type,
                    "thread_ts": thread_ts,
                },
            ),
        )

    add(
        "slack:db-migration-thread-992",
        "#db-migration - Thread: Migration blockers last week",
        "Channel: #db-migration (public)\n"
        "Thread started by: jdoe (2026-09-22 14:30)\n\n"
        "jdoe: Anyone seeing replication lag spikes during the "
        "morning peak? Seeing warnings.\n\n"
        "alice: 120ms at 9AM but settled to 40ms by 10AM. "
        "Fine for cutover.\n\n"
        "jdoe: Pool sizing test passed at 2x load. Clear for Friday.\n\n"
        "alice: Agreed. Go/no-go signal Thursday EOD.",
        _ts(2026, 9, 22, 15), 1,
        ["alice", "jdoe"],
        ["engineer", "senior_engineer", "admin"],
        channel="db-migration",
        thread_ts="992",
    )

    add(
        "slack:leadership-thread-120",
        "#leadership-private - Thread: Q3 budget concerns",
        "Channel: #leadership-private (private)\n"
        "Thread started by: frank (2026-09-20 09:00)\n\n"
        "frank: Q3 burn 8% above forecast. Tighten.\n"
        "erin: Finance reviewing. Projections by EOW.\n"
        "frank: Prioritize. Board meeting in two weeks.",
        _ts(2026, 9, 20, 10), 1,
        ["frank", "erin", "diana"],
        ["admin", "compliance_officer"],
        sensitivity=SensitivityLevel.RESTRICTED,
        channel="leadership-private",
        channel_type="private",
        thread_ts="120",
    )

    add(
        "slack:payment-incident-thread-45",
        "#payment-incident-private - Thread: 2026-09-14 outage",
        "Channel: #payment-incident-private (private)\n"
        "Thread started by: jdoe (2026-09-14 03:15)\n\n"
        "jdoe: Payment service down. Redis failover triggered.\n"
        "alice: Circuit breaker disabled. That's why it cascaded.\n"
        "jdoe: Manual failover to backup region.\n"
        "alice: Failover complete. Recovering.\n"
        "jdoe: 45 min outage. Creating RCA PAY-456.\n"
        "alice: Breaker disabled last Tuesday deploy. Re-enable ASAP.",
        _ts(2026, 9, 14, 4), 1,
        ["alice", "jdoe", "charlie"],
        ["admin"],
        sensitivity=SensitivityLevel.RESTRICTED,
        channel="payment-incident-private",
        channel_type="private",
        thread_ts="45",
    )

    add(
        "slack:payment-general-thread-7",
        "#payment-general - Thread: Circuit breaker follow-up",
        "Channel: #payment-general (public)\n"
        "Thread started by: alice (2026-09-18 10:00)\n\n"
        "alice: Circuit breaker re-enabled, 50% threshold. "
        "Integration test added to CI.\n\n"
        "jdoe: Should prevent the cascade from the 14th.",
        _ts(2026, 9, 18, 11), 1,
        ["alice", "jdoe"],
        ["engineer", "senior_engineer", "admin"],
        channel="payment-general",
        thread_ts="7",
    )

    add(
        "slack:eng-design-thread-33",
        "#eng-design - Thread: New auth service discussion",
        "Channel: #eng-design (public)\n"
        "Thread started by: alice (2026-09-12 16:00)\n\n"
        "alice: Design doc posted. OAuth 2.1 + PKCE.\n\n"
        "jdoe: Token refresh must be bulletproof or cascading "
        "auth failures.\n\n"
        "alice: Agreed. Graceful degradation: expired tokens "
        "trigger re-auth flow.\n\n"
        "jdoe: Good. Review in sprint planning.",
        _ts(2026, 9, 12, 17), 1,
        ["alice", "jdoe"],
        ["engineer", "senior_engineer", "admin"],
        channel="eng-design",
        thread_ts="33",
    )

    return resources


class SlackConnector(BaseConnector):
    """Mock Slack connector with channel-membership permissions."""

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