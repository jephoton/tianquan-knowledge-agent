"""Agents for VeriBrain.

- llm_client:  LLMClient protocol + deterministic StubLLMClient (ADR-0005).
- answer_agent: grounded, citation-validated answers (INV6/INV7).
- grounding_checker: hallucination detection — strips ungrounded sentences (INV8).
- orchestrator: end-to-end query -> retrieval -> audit -> answer -> grounding -> audit.
"""

from backend.agents.llm_client import LLMClient, StubLLMClient
from backend.agents.answer_agent import Answer, AnswerAgent, NO_ACCESS_MESSAGE
from backend.agents.grounding_checker import GroundingChecker, GroundingReport
from backend.agents.query_scanner import QueryScanner, InjectionReport
from backend.agents.orchestrator import Orchestrator, QueryResponse

__all__ = [
    "LLMClient",
    "StubLLMClient",
    "Answer",
    "AnswerAgent",
    "NO_ACCESS_MESSAGE",
    "GroundingChecker",
    "GroundingReport",
    "QueryScanner",
    "InjectionReport",
    "Orchestrator",
    "QueryResponse",
]
