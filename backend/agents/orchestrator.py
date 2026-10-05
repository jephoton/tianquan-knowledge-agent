"""Orchestrator.

Routes a user query through the full Tianquan pipeline:

    query
      -> retrieval (candidate search -> permission filter -> context assembler)
      -> audit every policy decision (allow AND deny)  [INV4]
      -> answer agent (grounded, citation-validated)   [INV6]
      -> grounding checker (ungrounded sentences stripped) [INV8]
      -> audit the answer event
    -> return {answer, citations, decisions, audit_chain_head}

This is the single entry point the demo / API layer calls. Authorization is
already enforced upstream (the answer agent only sees filtered context), so the
orchestrator's job is sequencing and audit, not access control.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from backend.agents.answer_agent import Answer, AnswerAgent
from backend.agents.grounding_checker import GroundingChecker, GroundingReport
from backend.agents.llm_client import LLMClient, StubLLMClient
from backend.agents.query_scanner import QueryScanner, InjectionReport
from backend.audit.hash_chain import HashChain
from backend.connectors.base import BaseConnector
from backend.models import Action, Decision, User
from backend.policy.admin import PermissionAdmin
from backend.retrieval.context_assembler import Citation
from backend.retrieval.pipeline import RetrievalPipeline


@dataclass
class QueryResponse:
    """The orchestrator's response to a query (architecture.md §5)."""

    query_id: str
    answer: str
    citations: list[Citation] = field(default_factory=list)
    decisions: list[Decision] = field(default_factory=list)
    audit_chain_head: str = ""
    no_access: bool = False

    @property
    def allow_count(self) -> int:
        return sum(1 for d in self.decisions if d.result.value == "allow")

    @property
    def deny_count(self) -> int:
        return sum(1 for d in self.decisions if d.result.value == "deny")


class Orchestrator:
    """End-to-end query handler: retrieval -> audit -> answer -> audit."""

    def __init__(
        self,
        connectors: list[BaseConnector],
        llm: LLMClient | None = None,
        audit_chain: HashChain | None = None,
        max_context_chars: int = 8000,
        grounding_checker: GroundingChecker | None = None,
    ):
        self._connectors = list(connectors)
        self._pipeline = RetrievalPipeline(
            self._connectors, max_context_chars=max_context_chars,
        )
        self._answer_agent = AnswerAgent(llm or StubLLMClient())
        self._audit = audit_chain or HashChain()
        self._admin = PermissionAdmin(self._connectors)
        self._grounding_checker = grounding_checker or GroundingChecker()
        self._query_scanner = QueryScanner()

    @property
    def audit(self) -> HashChain:
        """The audit chain (for inspection / query in the demo)."""
        return self._audit

    @property
    def admin(self) -> PermissionAdmin:
        """Live permission admin over the SAME connectors the pipeline uses.

        A revoke/grant here is reflected in the next `handle` call without a
        reindex, because the permission filter re-fetches live ACLs (Demo 3).
        """
        return self._admin

    def reindex(self) -> int:
        return self._pipeline.reindex()

    def export(self, user: User, resource_ids: list[str]) -> dict:
        """Re-check EXPORT permission per resource for `user` and audit it.

        Export is a distinct, higher-bar action than read (a user may read a
        blended answer in-session but not export every source out of the
        audited environment). Each resource is re-decided with Action.EXPORT
        against the LIVE ACL and recorded in the audit trail. Returns the
        resources the user may export and those denied.
        """
        from backend.policy.policy_engine import PolicyEngine
        from backend.models import DecisionResult

        engine = PolicyEngine()
        query_id = str(uuid.uuid4())
        allowed: list[str] = []
        denied: list[str] = []
        decisions: list[Decision] = []

        for rid in resource_ids:
            resource = None
            for connector in self._connectors:
                resource = connector.get_resource(rid)
                if resource is not None:
                    break
            if resource is None:
                denied.append(rid)
                continue
            decision = engine.decide(user, resource, Action.EXPORT)
            decisions.append(decision)
            if decision.result == DecisionResult.ALLOW:
                allowed.append(rid)
            else:
                denied.append(rid)

        self._audit.append_decisions(decisions, query_id)
        return {
            "query_id": query_id,
            "allowed": allowed,
            "denied": denied,
            "all_allowed": len(denied) == 0 and len(allowed) > 0,
        }

    def handle(
        self,
        user: User,
        query: str,
        k: int = 10,
        action: Action = Action.READ,
    ) -> QueryResponse:
        """Handle a query end to end and return the response.

        Every policy decision is audited before the answer is generated, so
        the audit trail reflects the authorization outcome regardless of what
        the answer step does (INV4).
        """
        query_id = str(uuid.uuid4())

        # 0. Prompt-injection scan — flag suspicious queries for audit.
        #    Does NOT block the query; the permission system is the real guard.
        injection_report = self._query_scanner.scan(query)

        # 1. Retrieval (search -> filter -> assemble). Only authorized content
        #    reaches the assembled context.
        retrieval = self._pipeline.run(user, query, k=k, action=action)

        # 2. Audit every decision (allow and deny) under this query.
        self._audit.append_decisions(retrieval.outcome.decisions, query_id)

        # 3. Answer from the authorized context (citation-validated, no-leak).
        #    If the live LLM client fails at runtime (e.g. network/TLS error
        #    reaching the ADP endpoint), degrade gracefully to the stub rather
        #    than failing the whole request. The stub still answers only from
        #    the already-filtered context, so safety (INV1/INV2) is preserved.
        try:
            answer: Answer = self._answer_agent.answer(query, retrieval.context)
        except Exception:
            from backend.agents.answer_agent import AnswerAgent
            from backend.agents.llm_client import StubLLMClient
            fallback_agent = AnswerAgent(StubLLMClient())
            answer = fallback_agent.answer(query, retrieval.context)

        # 3b. Grounding check — strip hallucinated sentences (INV8).
        #     Skipped on no-access (empty context) — the canonical message
        #     is not an LLM generation.
        #     If everything is stripped (which can happen with the stub LLM
        #     whose vocabulary doesn't match the context), fall back to a
        #     minimal grounded statement rather than an empty string.
        grounding_report: GroundingReport | None = None
        if not answer.no_access:
            grounding_report = self._grounding_checker.check(
                answer.text, retrieval.context,
            )
            if grounding_report.grounded_text:
                answer.text = grounding_report.grounded_text
            else:
                # All sentences were stripped — the LLM produced nothing
                # grounded. Fall back to a citation-only summary so the
                # user still sees which sources were authorized.
                markers = " ".join(c.marker for c in answer.citations)
                answer.text = f"Relevant sources found: {markers}." if markers else ""

        # 4. Audit the answer emission as its own event (resource_id=None).
        #    If injection was suspected, the reason field carries the flag
        #    so security teams can review suspicious queries in the audit trail.
        reason = "answer_no_access" if answer.no_access else "answer_generated"
        if injection_report.suspicious:
            reason += f"[injection_suspected:{injection_report.risk_level}]"
        answer_decision = Decision(
            user_id=user.user_id,
            resource_id=None,  # answer event is not tied to one resource
            action=action,
            result=_answer_result(answer),
            reason=reason,
            acl_version=0,
            policy_version=0,
        )
        self._audit.append_decision(answer_decision, query_id)

        return QueryResponse(
            query_id=query_id,
            answer=answer.text,
            citations=answer.citations,
            decisions=retrieval.outcome.decisions,
            audit_chain_head=self._audit.head_hash(),
            no_access=answer.no_access,
        )


def _answer_result(answer: Answer):
    """Map an answer to a DecisionResult for the audit event."""
    from backend.models import DecisionResult

    # An answer emission is recorded as an "allow" (an answer was served);
    # a no-access response is recorded as a "deny" (nothing was served).
    return DecisionResult.DENY if answer.no_access else DecisionResult.ALLOW
