"""Orchestrator.

Routes a user query through the full VeriBrain pipeline:

    query
      -> retrieval (candidate search -> permission filter -> context assembler)
      -> audit every policy decision (allow AND deny)  [INV4]
      -> answer agent (grounded, citation-validated)   [INV6]
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
from backend.agents.llm_client import LLMClient, StubLLMClient
from backend.audit.hash_chain import HashChain
from backend.connectors.base import BaseConnector
from backend.models import Action, Decision, User
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
    ):
        self._pipeline = RetrievalPipeline(
            connectors, max_context_chars=max_context_chars,
        )
        self._answer_agent = AnswerAgent(llm or StubLLMClient())
        self._audit = audit_chain or HashChain()

    @property
    def audit(self) -> HashChain:
        """The audit chain (for inspection / query in the demo)."""
        return self._audit

    def reindex(self) -> int:
        return self._pipeline.reindex()

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

        # 1. Retrieval (search -> filter -> assemble). Only authorized content
        #    reaches the assembled context.
        retrieval = self._pipeline.run(user, query, k=k, action=action)

        # 2. Audit every decision (allow and deny) under this query.
        self._audit.append_decisions(retrieval.outcome.decisions, query_id)

        # 3. Answer from the authorized context (citation-validated, no-leak).
        answer: Answer = self._answer_agent.answer(query, retrieval.context)

        # 4. Audit the answer emission as its own event (resource_id=None).
        answer_decision = Decision(
            user_id=user.user_id,
            resource_id=None,  # answer event is not tied to one resource
            action=action,
            result=_answer_result(answer),
            reason="answer_no_access" if answer.no_access else "answer_generated",
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
