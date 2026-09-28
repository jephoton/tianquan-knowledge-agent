"""LLM client abstraction.

The answer agent depends on this interface, never a concrete provider SDK
(see ADR-0005). The permission-safety guarantee lives in the retrieval
pipeline — the LLM only ever receives already-filtered context — so the
model is a swappable component behind a trust boundary.

Implementations:
- StubLLMClient: deterministic, offline, used for tests and CI.
- (later) a Tencent Cloud LLM adapter (WorkBuddy/ADP) for the demo, added
  without changing the answer agent.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMClient(Protocol):
    """Minimal interface the answer agent needs from an LLM.

    `generate` receives a fully-assembled prompt whose context section
    already contains ONLY authorized content. The client must not fetch
    or invent additional content.
    """

    def generate(self, prompt: str) -> str:
        """Return the model's completion for the given prompt."""
        ...


class StubLLMClient:
    """Deterministic, offline stub for tests and development.

    Produces a grounded, citation-bearing answer by echoing the citation
    markers present in the prompt's context. It never introduces content
    beyond what the prompt contains, which lets tests assert grounding and
    citation properties deterministically.
    """

    def generate(self, prompt: str) -> str:
        # The prompt embeds context blocks headed by markers like "[1] ...".
        # The stub "answers" by acknowledging the cited sources it was given.
        import re

        markers = re.findall(r"\[\d+\]", prompt)
        # Preserve order, drop duplicates.
        seen: list[str] = []
        for m in markers:
            if m not in seen:
                seen.append(m)

        if not seen:
            # No context was provided — the agent layer handles the no-leak
            # message, but if the stub is called directly we stay neutral.
            return "No sources were provided."

        cites = " ".join(seen)
        return (
            "Based on the available sources, here is a grounded summary "
            f"drawing on {cites}."
        )
