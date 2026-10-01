"""Answer agent.

Generates a grounded, cited answer from an AssembledContext using an
LLMClient. The agent enforces two invariants at the answer boundary:

- INV6 (NoUnauthorizedCitation): every citation in the returned answer must
  correspond to a resource actually present in the authorized context. Any
  citation the model emits that is not authorized is stripped.
- INV7 (NoMetadataLeakOnDeny): when the authorized context is empty, the agent
  returns the canonical no-leak message and cites nothing — it never reveals
  that restricted content exists.

The agent only ever sees the assembled (already-filtered) context, so it
cannot leak content it never received. This module is about grounding and
citation hygiene, not authorization.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from backend.agents.llm_client import LLMClient
from backend.retrieval.context_assembler import AssembledContext, Citation

# Shown to the user when nothing authorized matched. Must not reveal whether
# restricted content exists (INV7 / Demo 2).
NO_ACCESS_MESSAGE = (
    "I could not find accessible information matching your request."
)

_CITATION_RE = re.compile(r"\[(\d+)\]")

_SYSTEM_PREAMBLE = (
    "You are Tianquan (天权). Answer the user's question using ONLY the numbered "
    "sources in the context below. Cite sources with their bracketed markers "
    "(e.g. [1]). Do not use any information not present in the context. If the "
    "context is empty, say you could not find accessible information."
)


@dataclass
class Answer:
    """The answer agent's output.

    Attributes:
        text: The answer text (citations validated).
        citations: The citations actually supported by the context.
        grounded: True if the answer was produced from non-empty context.
        no_access: True if the no-metadata-leak message was returned.
    """

    text: str
    citations: list[Citation] = field(default_factory=list)
    grounded: bool = True
    no_access: bool = False


class AnswerAgent:
    """Produces grounded, citation-validated answers."""

    def __init__(self, llm: LLMClient):
        self._llm = llm

    def build_prompt(self, question: str, context: AssembledContext) -> str:
        """Assemble the full prompt sent to the LLM."""
        return (
            f"{_SYSTEM_PREAMBLE}\n\n"
            f"# Question\n{question}\n\n"
            f"# Context\n{context.text}\n"
        )

    def answer(self, question: str, context: AssembledContext) -> Answer:
        """Generate an answer grounded in the authorized context.

        Empty context -> canonical no-leak message (INV7). Otherwise generate
        via the LLM and strip any citation not backed by the context (INV6).
        """
        if not context.included_resource_ids:
            return Answer(
                text=NO_ACCESS_MESSAGE,
                citations=[],
                grounded=False,
                no_access=True,
            )

        prompt = self.build_prompt(question, context)
        raw = self._llm.generate(prompt)
        clean_text, valid_citations = self._validate_citations(raw, context)

        return Answer(
            text=clean_text,
            citations=valid_citations,
            grounded=True,
            no_access=False,
        )

    # -- INV6 enforcement ----------------------------------------------

    def _validate_citations(
        self, text: str, context: AssembledContext,
    ) -> tuple[str, list[Citation]]:
        """Strip citation markers not backed by the authorized context.

        Returns the cleaned text and the list of citations that are valid
        (i.e. their marker maps to an in-context, authorized resource).
        """
        valid_markers = {c.marker for c in context.citations}
        marker_to_citation = {c.marker: c for c in context.citations}

        used: list[Citation] = []
        seen_markers: set[str] = set()

        def _replace(match: re.Match) -> str:
            marker = match.group(0)  # e.g. "[2]"
            if marker in valid_markers:
                if marker not in seen_markers:
                    seen_markers.add(marker)
                    used.append(marker_to_citation[marker])
                return marker
            # Unauthorized / hallucinated citation -> strip it.
            return ""

        cleaned = _CITATION_RE.sub(_replace, text)
        # Collapse any double spaces left by stripped markers.
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()

        # Preserve citation order as they appear in the context.
        used.sort(key=lambda c: context.citations.index(c))
        return cleaned, used
