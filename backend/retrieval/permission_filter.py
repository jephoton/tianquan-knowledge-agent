"""Permission filter — the pre-LLM authorization gate.

Takes candidate resources from candidate search and filters them through
the policy engine so that only authorized content proceeds to the context
assembler. This is the enforcement point for INV1 (RetrievedOnlyIfAuthorized)
and INV2 (LLMSeesOnlyRetrievedContent).

Safety-critical design:
- The filter ALWAYS re-fetches the live ACL from the owning connector and
  evaluates against a resource carrying that live ACL. It never trusts the
  indexed snapshot for authorization. This means a stale index can surface a
  candidate, but a revoked permission is honored immediately (INV3).
- Freshness is checked and recorded per candidate so staleness is observable
  (for the audit trail and the policy inspector UI), but authorization is
  decided from the live ACL regardless.
- Denied candidates are dropped entirely. The returned allowed set is all the
  context assembler — and therefore the LLM — will ever see.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from backend.models import Action, Decision, DecisionResult, Resource
from backend.policy.freshness_checker import FreshnessResult, check_freshness
from backend.policy.policy_engine import PolicyEngine
from backend.retrieval.candidate_search import ScoredCandidate


@dataclass
class FilteredCandidate:
    """A candidate that passed the permission filter.

    Attributes:
        resource: The resource carrying its LIVE ACL (not the indexed snapshot).
        decision: The ALLOW decision from the policy engine.
        score: The relevance score from candidate search.
        freshness: Result of comparing indexed vs live ACL version.
    """

    resource: Resource
    decision: Decision
    score: float
    freshness: FreshnessResult


@dataclass
class FilterOutcome:
    """Full outcome of filtering a candidate set.

    Attributes:
        allowed: Candidates that passed (in input order). Only these reach
            the context assembler / LLM.
        decisions: Every decision made (allow AND deny), for the audit trail.
    """

    allowed: list[FilteredCandidate]
    decisions: list[Decision]

    @property
    def allowed_resources(self) -> list[Resource]:
        """Convenience: the authorized resources with live ACLs."""
        return [c.resource for c in self.allowed]


class PermissionFilter:
    """Filters candidate resources through the policy engine, pre-LLM."""

    def __init__(self, engine: PolicyEngine | None = None):
        self._engine = engine or PolicyEngine()

    def _live_resource(self, candidate: ScoredCandidate) -> Resource:
        """Return the candidate's resource carrying its LIVE ACL.

        Re-fetches the current ACL from the owning connector. Falls back to
        the snapshot resource only if the connector no longer knows the ACL
        (treated as fail-closed by the policy engine downstream).
        """
        connector = candidate.entry.connector
        live_acl = connector.get_acl(candidate.resource.resource_id)
        if live_acl is None:
            return candidate.resource
        # Rebuild the resource with the live ACL so the policy engine and the
        # decision's acl_version reflect current permissions, not the snapshot.
        return replace(candidate.resource, acl=live_acl)

    def filter(
        self,
        user,
        candidates: list[ScoredCandidate],
        action: Action = Action.READ,
    ) -> FilterOutcome:
        """Filter candidates for a user, returning allowed set + all decisions.

        Denied candidates are excluded from `allowed` entirely — they never
        reach the LLM. Every decision (allow and deny) is recorded for audit.
        """
        allowed: list[FilteredCandidate] = []
        decisions: list[Decision] = []

        for candidate in candidates:
            live_resource = self._live_resource(candidate)
            freshness = check_freshness(
                live_resource, candidate.entry.indexed_acl_version,
            )
            decision = self._engine.decide(user, live_resource, action)
            decisions.append(decision)

            if decision.result == DecisionResult.ALLOW:
                allowed.append(
                    FilteredCandidate(
                        resource=live_resource,
                        decision=decision,
                        score=candidate.score,
                        freshness=freshness,
                    )
                )

        return FilterOutcome(allowed=allowed, decisions=decisions)
