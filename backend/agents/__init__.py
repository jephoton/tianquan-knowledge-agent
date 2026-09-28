"""Agents for VeriBrain.

- llm_client:  LLMClient protocol + deterministic StubLLMClient (ADR-0005).
- answer_agent: grounded, citation-validated answers (INV6/INV7).
- orchestrator: end-to-end query -> retrieval -> audit -> answer -> audit.
"""

from backend.agents.llm_client import LLMClient, StubLLMClient
from backend.agents.answer_agent import Answer, AnswerAgent, NO_ACCESS_MESSAGE
from backend.agents.orchestrator import Orchestrator, QueryResponse

__all__ = [
    "LLMClient",
    "StubLLMClient",
    "Answer",
    "AnswerAgent",
    "NO_ACCESS_MESSAGE",
    "Orchestrator",
    "QueryResponse",
]
