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

# Regex to detect "lazy" answers that are just citation pointers with no
# real informational content — e.g. "see [1] [2] [3]" or "refer to [1]".
_LAZY_PATTERNS = [
    re.compile(
        r"^(see|refer to|check|look at|view|consult)\b.*\[\d+\]", re.IGNORECASE
    ),
    re.compile(
        r"^(see|refer to|check|look at|view|consult)\b.*\[\d+\].*\[\d+\]",
        re.IGNORECASE,
    ),
]

_REINFORCEMENT_PROMPT = (
    "Your previous answer was too vague — it only pointed at references "
    "without stating the actual information. Please answer again, this time "
    "writing a COMPLETE, self-contained answer that states the facts directly. "
    "Do NOT say 'see references' or 'refer to'. State the actual content."
)

_MAX_RETRIES = 2

_SYSTEM_PREAMBLE = (
    "You are Tianquan (天权). Answer the user's question using ONLY the numbered "
    "sources in the context below.\n\n"
    "CRITICAL RULES:\n"
    "1. Your answer must be SELF-CONTAINED — a reader should understand the full "
    "answer WITHOUT looking at the source list. Synthesize the actual facts, "
    "status, dates, and details from the context into a complete sentence.\n"
    "2. Do NOT write lazy pointer answers like \"see references [1]\" or "
    "\"refer to [1] [2] [3]\" — always state the actual information.\n"
    "3. Cite sources with bracketed markers (e.g. [1]) AFTER the relevant "
    "statement, not as a standalone reference.\n"
    "4. Do not use any information not present in the context.\n"
    "5. If the context is empty, say you could not find accessible information."
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

        # Retry if the answer is just a lazy pointer to references.
        for _ in range(_MAX_RETRIES):
            if not self._is_lazy(clean_text):
                break
            raw = self._llm.generate(
                prompt + "\n\n" + _REINFORCEMENT_PROMPT
            )
            clean_text, valid_citations = self._validate_citations(raw, context)

        return Answer(
            text=clean_text,
            citations=valid_citations,
            grounded=True,
            no_access=False,
        )

    @staticmethod
    def _is_lazy(text: str) -> bool:
        """Return True if the answer is just citation pointers, not real info.

        Detects patterns like "See [1] [2]" or "Refer to [1]" where the entire
        answer line is a directive to look at references rather than stating
        the actual information.
        """
        stripped = text.strip()
        if not stripped:
            return True

        # If the answer is very short and mostly citation markers, it's lazy.
        citation_chars = len(_CITATION_RE.findall(stripped))
        non_citation_text = _CITATION_RE.sub("", stripped).strip()
        if len(non_citation_text) < 20 and citation_chars > 0:
            return True

        # Check explicit lazy patterns.
        for pattern in _LAZY_PATTERNS:
            if pattern.match(stripped):
                return True

        return False

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
