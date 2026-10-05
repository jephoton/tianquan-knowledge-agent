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

    Produces a grounded answer by extractive summarization: it pulls the
    most informative sentences from the authorized context blocks and
    stitches them into a cited summary. Because the output is composed of
    real context sentences (each tagged with its citation marker), it
    survives the grounding check (INV8) and reads like a genuine answer
    rather than templated filler — while never introducing content beyond
    the context it was given.
    """

    def generate(self, prompt: str) -> str:
        import re

        # The prompt has a "# Context" section with blocks headed by markers
        # like "[1] source:id — Title" followed by body lines.
        context = prompt.split("# Context", 1)[-1]

        # Split into citation blocks keyed by marker.
        blocks = re.split(r"(?=\[\d+\]\s)", context)
        summary_parts: list[str] = []
        for block in blocks:
            m = re.match(r"(\[\d+\])", block.strip())
            if not m:
                continue
            marker = m.group(1)
            # Take the first substantive sentence from the block body.
            body = block[m.end():]
            # Drop the "source:id — Title" header line.
            lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
            body_lines = lines[1:] if len(lines) > 1 else lines
            sentence = _first_sentence(" ".join(body_lines))
            if sentence:
                summary_parts.append(f"{sentence} {marker}")

        if not summary_parts:
            return ""  # agent layer handles empty/no-access

        return " ".join(summary_parts)


def _first_sentence(text: str, max_len: int = 220) -> str:
    """Return the first sentence of `text`, trimmed to a sane length."""
    text = text.strip()
    if not text:
        return ""
    # Split on sentence terminators; fall back to the whole string.
    import re
    parts = re.split(r"(?<=[.!?])\s+", text)
    sentence = parts[0].strip() if parts else text
    if len(sentence) > max_len:
        sentence = sentence[:max_len].rsplit(" ", 1)[0] + "…"
    return sentence
