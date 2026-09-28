"""Retrieval pipeline — wires the four M3 stages together.

    query -> candidate_search -> permission_filter -> context_assembler

This is the permission-aware retrieval path. Given a user and a query, it
returns an assembled context containing ONLY content the user is authorized
to see, plus the full set of policy decisions (allow and deny) for the audit
trail and the policy inspector UI.

The pipeline is the single place the demo and the (future) orchestrator call
to go from a question to a safe, cited context.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.connectors.base import BaseConnector
from backend.models import Action, Decision, User
from backend.retrieval.candidate_search import CandidateSearch
from backend.retrieval.context_assembler import AssembledContext, ContextAssembler
from backend.retrieval.indexer import Indexer
from backend.retrieval.permission_filter import FilterOutcome, PermissionFilter


@dataclass
class RetrievalResult:
    """Result of running the retrieval pipeline for a query.

    Attributes:
        context: The assembled, authorized, cited context for the LLM.
        outcome: The permission-filter outcome (allowed set + all decisions).
        candidate_count: How many candidates search surfaced before filtering.
    """

    context: AssembledContext
    outcome: FilterOutcome
    candidate_count: int

    @property
    def decisions(self) -> list[Decision]:
        """All policy decisions made during retrieval (allow and deny)."""
        return self.outcome.decisions


class RetrievalPipeline:
    """End-to-end permission-aware retrieval."""

    def __init__(
        self,
        connectors: list[BaseConnector],
        max_context_chars: int = 8000,
    ):
        self._indexer = Indexer(connectors=list(connectors))
        self._indexer.reindex()
        self._search = CandidateSearch(self._indexer)
        self._filter = PermissionFilter()
        self._assembler = ContextAssembler(max_chars=max_context_chars)

    def reindex(self) -> int:
        """Rebuild the index (e.g. after seed data changes). Returns size."""
        return self._indexer.reindex()

    def run(
        self,
        user: User,
        query: str,
        k: int = 10,
        action: Action = Action.READ,
    ) -> RetrievalResult:
        """Run search -> filter -> assemble for a user's query.

        The permission filter re-fetches live ACLs, so revocations applied
        after indexing are honored without an explicit reindex.
        """
        candidates = self._search.search(query, k=k)
        outcome = self._filter.filter(user, candidates, action=action)
        context = self._assembler.assemble(outcome.allowed)
        return RetrievalResult(
            context=context,
            outcome=outcome,
            candidate_count=len(candidates),
        )
