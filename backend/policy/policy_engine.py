"""Policy engine — the authorization core.

Given (user, resource, action), produces a Decision with:
- allow/deny result
- human-readable reason
- ACL version at decision time
- policy version

Decision order (fail-closed):
1. User existence check.
2. Resource existence check.
3. Deny-list override (explicit denied_users in ACL).
4. Source-specific permission rules.
5. Sensitivity clearance check.
6. Action permission check (role-based).
7. If all gates pass: ALLOW.

The deny-list at step 3 is redundant with source-specific checks
but provides a belt-and-suspenders guarantee that no source-specific
logic can accidentally bypass an explicit deny.
"""

from __future__ import annotations

from backend.models import (
    Action,
    ACL,
    Decision,
    DecisionResult,
    Resource,
    User,
    utc_now,
)
from backend.policy.permission_mapping import (
    check_action_permission,
    check_sensitivity_clearance,
    check_source_specific,
)

POLICY_VERSION = 1


class PolicyEngine:
    """Authorization decision engine.

    The engine is stateless — it does not cache decisions. Every call
    reads the live ACL from the resource, ensuring that revocations
    are reflected immediately (INV3: RevokedAccessNotReusable).
    """

    def decide(
        self, user: User, resource: Resource, action: Action,
    ) -> Decision:
        """Evaluate whether user may perform action on resource.

        Returns a Decision. Never raises — denies are returned, not thrown.
        """
        acl_version = resource.acl.acl_version

        # Gate 3: Explicit deny-list override.
        if user.user_id in resource.acl.denied_users:
            return Decision(
                user_id=user.user_id,
                resource_id=resource.resource_id,
                action=action,
                result=DecisionResult.DENY,
                reason="explicit_deny_list",
                acl_version=acl_version,
                policy_version=POLICY_VERSION,
                timestamp=utc_now(),
            )

        # Gate 4: Source-specific permission rules.
        src_ok, src_reason = check_source_specific(user, resource)
        if not src_ok:
            return Decision(
                user_id=user.user_id,
                resource_id=resource.resource_id,
                action=action,
                result=DecisionResult.DENY,
                reason=src_reason,
                acl_version=acl_version,
                policy_version=POLICY_VERSION,
                timestamp=utc_now(),
            )

        # Gate 5: Sensitivity clearance.
        sens_ok, sens_reason = check_sensitivity_clearance(user, resource)
        if not sens_ok:
            return Decision(
                user_id=user.user_id,
                resource_id=resource.resource_id,
                action=action,
                result=DecisionResult.DENY,
                reason=sens_reason,
                acl_version=acl_version,
                policy_version=POLICY_VERSION,
                timestamp=utc_now(),
            )

        # Gate 6: Action permission (role-based).
        act_ok, act_reason = check_action_permission(user, action)
        if not act_ok:
            return Decision(
                user_id=user.user_id,
                resource_id=resource.resource_id,
                action=action,
                result=DecisionResult.DENY,
                reason=act_reason,
                acl_version=acl_version,
                policy_version=POLICY_VERSION,
                timestamp=utc_now(),
            )

        # All gates passed.
        return Decision(
            user_id=user.user_id,
            resource_id=resource.resource_id,
            action=action,
            result=DecisionResult.ALLOW,
            reason=src_reason,
            acl_version=acl_version,
            policy_version=POLICY_VERSION,
            timestamp=utc_now(),
        )

    def decide_many(
        self, user: User, resources: list[Resource], action: Action,
    ) -> list[Decision]:
        """Evaluate action for multiple resources.

        Convenience method for the retrieval pipeline: filter a
        candidate set and return decisions for all resources.
        """
        return [self.decide(user, r, action) for r in resources]

    def filter_allowed(
        self, user: User, resources: list[Resource], action: Action,
    ) -> list[tuple[Resource, Decision]]:
        """Return only (resource, decision) pairs where the decision is ALLOW.

        Used by the permission filter in the retrieval pipeline.
        Denied resources are excluded entirely — the LLM never sees them.
        """
        results: list[tuple[Resource, Decision]] = []
        for r in resources:
            d = self.decide(user, r, action)
            if d.result == DecisionResult.ALLOW:
                results.append((r, d))
        return results