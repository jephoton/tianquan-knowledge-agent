"""Grounding checker — hallucination detection layer (INV8).

Runs **after** the LLM generates an answer but **before** it is returned to the
user. Compares every sentence in the answer against the authorized context and
strips sentences that are not sufficiently grounded.

Two deterministic checks, no external model needed:

- **Lexical overlap** — each answer sentence is tokenized and compared against
  the context. Sentences with token overlap below a threshold are flagged.
- **Entity extraction** — capitalized phrases, numbers, and technical terms in
  the answer are checked for presence in the context. Terms not found anywhere
  in the context increase the hallucination suspicion for that sentence.

This enforces INV8 (GroundedAnswerOnly): every sentence in the returned answer
must have sufficient lexical overlap with the authorized context. Ungrounded
sentences are stripped, mirroring the existing INV6 citation-stripping pattern.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from backend.retrieval.context_assembler import AssembledContext

# --- Configuration -------------------------------------------------------

#: Minimum token-overlap ratio for a sentence to be considered grounded.
#: 0.3 means at least 30% of the sentence's content tokens must appear in
#: the context.
MIN_OVERLAP_RATIO = 0.3

#: Minimum number of tokens a sentence must have before grounding is checked.
#: Very short sentences (e.g. "Yes." or "See [1].") are always kept — they
#: can't meaningfully be checked for overlap and are usually connective tissue.
MIN_SENTENCE_TOKENS = 4

# --- Stopwords — excluded from overlap calculation -----------------------

_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "if", "then", "else", "when",
    "at", "by", "for", "with", "about", "against", "between", "into",
    "through", "during", "before", "after", "above", "below", "to", "from",
    "up", "down", "in", "out", "on", "off", "over", "under", "again",
    "further", "is", "are", "was", "were", "be", "been", "being", "am",
    "have", "has", "had", "having", "do", "does", "did", "doing", "will",
    "would", "shall", "should", "may", "might", "must", "can", "could",
    "of", "as", "this", "that", "these", "those", "it", "its", "they",
    "them", "their", "there", "here", "which", "who", "whom", "whose",
    "what", "not", "no", "nor", "so", "than", "too", "very", "just",
    "also", "only", "own", "same", "such", "s", "t",
})


# --- Data structures -----------------------------------------------------

@dataclass
class GroundingReport:
    """Result of checking an answer against the context.

    Attributes:
        grounded_text: The answer text with ungrounded sentences removed.
        total_sentences: Total sentences in the original answer.
        grounded_sentences: Sentences that passed the grounding check.
        ungrounded_sentences: Sentences that were stripped.
        confidence: Fraction of sentences that were grounded (0.0–1.0).
        grounded: True if all sentences were grounded (nothing stripped).
    """

    grounded_text: str
    total_sentences: int
    grounded_sentences: list[str] = field(default_factory=list)
    ungrounded_sentences: list[str] = field(default_factory=list)
    confidence: float = 1.0
    grounded: bool = True


# --- Tokenization helpers ------------------------------------------------

def _tokenize(text: str) -> list[str]:
    """Split text into lowercase word tokens, stripping punctuation."""
    return re.findall(r"[a-zA-Z0-9]+", text.lower())


def _content_tokens(tokens: list[str]) -> list[str]:
    """Filter out stopwords and single characters."""
    return [t for t in tokens if len(t) > 1 and t not in _STOPWORDS]


def _sentences(text: str) -> list[str]:
    """Split text into sentences.

    Handles common abbreviations minimally. Citation markers like [1] are
    preserved within their sentence.
    """
    # Protect common abbreviations from being split.
    protected = text.replace("e.g.", "<EG>").replace("i.e.", "<IE>")
    # Split on sentence-ending punctuation followed by whitespace + capital.
    raw = re.split(r'(?<=[.!?])\s+(?=[A-Z"])', protected)
    # Restore abbreviations and strip whitespace.
    return [s.replace("<EG>", "e.g.").replace("<IE>", "i.e.").strip() for s in raw if s.strip()]


# --- Entity extraction ---------------------------------------------------

# Capitalized phrases: "PostgreSQL", "Olympus Mons", "SQL Injection"
# Matches: Capitalized word (min 2 chars), optionally followed by more
# capitalized words. Handles CamelCase and ALLCAPS.
_ENTITY_RE = re.compile(r"\b([A-Z][A-Za-z]{1,}(?:\s+[A-Z][A-Za-z]{1,})*)\b")
# Numbers (including decimals, percentages, versions)
_NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?%?\b")
# Technical terms (hyphenated or camelCase)
_TECH_RE = re.compile(r"\b(?:[a-z]+-[a-z]+|[a-z]+[A-Z][a-z]+)\b")


def _extract_entities(text: str) -> set[str]:
    """Extract entities and significant terms from text.

    Excludes sentence-initial articles ("The", "A", "An") which are not
    entities — they're just capitalized because they start a sentence.
    """
    entities: set[str] = set()

    for match in _ENTITY_RE.finditer(text):
        val = match.group(1).lower()
        if val in ("the", "a", "an"):
            continue
        entities.add(val)

    for match in _NUMBER_RE.finditer(text):
        entities.add(match.group(0))

    for match in _TECH_RE.finditer(text):
        entities.add(match.group(0).lower())

    return entities


# --- The checker ---------------------------------------------------------


class GroundingChecker:
    """Checks whether an LLM answer is grounded in the authorized context.

    Usage::

        report = checker.check(raw_answer_text, context)
        return report.grounded_text  # stripped answer

    When the context is empty (no-access case), the checker is a no-op —
    the answer agent already handles that case with the canonical message.
    """

    def __init__(self, min_overlap: float = MIN_OVERLAP_RATIO):
        self._min_overlap = min_overlap

    def check(self, answer_text: str, context: AssembledContext) -> GroundingReport:
        """Check an answer for grounding and return a report.

        Sentences with insufficient lexical overlap with the context are
        stripped. Citation markers ([1], [2], etc.) are preserved on
        grounded sentences and removed along with their ungrounded sentence.
        """
        # No context → nothing to check (the no-access path handles this).
        if not context.included_resource_ids or not context.text.strip():
            return GroundingReport(
                grounded_text=answer_text,
                total_sentences=0,
                grounded=True,
            )

        context_tokens = set(_content_tokens(_tokenize(context.text)))
        context_entities = _extract_entities(context.text)

        all_sentences = _sentences(answer_text)
        grounded: list[str] = []
        ungrounded: list[str] = []

        for sentence in all_sentences:
            sent_tokens = _content_tokens(_tokenize(sentence))

            # Short sentences are always kept (connective tissue, citations).
            if len(sent_tokens) < MIN_SENTENCE_TOKENS:
                grounded.append(sentence)
                continue

            # Layer 1: lexical overlap.
            if sent_tokens:
                overlap = len(context_tokens & set(sent_tokens)) / len(sent_tokens)
            else:
                overlap = 0.0

            # Layer 2: entity check — are named entities, numbers, and technical
            # terms in the context? If the sentence introduces entities not
            # found anywhere in the context, that's hallucination.
            # Common-word paraphrasing (synonyms, word-form changes) is
            # tolerated because overlap covers that — only *named* entities
            # (capitalized words, numbers, hyphenated terms) are checked here.
            sent_entities = _extract_entities(sentence)
            # Entities that are citation markers [1] are always fine.
            non_marker_entities = {
                e for e in sent_entities
                if not re.fullmatch(r"\[\d+\]", e)
            }
            missing_entities = non_marker_entities - context_entities - context_tokens

            # A sentence is grounded if BOTH:
            # - overlap >= threshold (sufficient lexical overlap with context)
            # - no entities are missing (all named terms appear in context)
            # This catches two hallucination patterns:
            #   1. High overlap but introduces new named entity (SQL injection)
            #   2. No missing entities but zero overlap (generic filler text)
            has_overlap = overlap >= self._min_overlap
            no_missing = len(missing_entities) == 0
            is_grounded = has_overlap and no_missing

            if is_grounded:
                grounded.append(sentence)
            else:
                ungrounded.append(sentence)

        grounded_text = " ".join(grounded).strip()
        # Clean up double spaces from joins.
        grounded_text = re.sub(r"\s{2,}", " ", grounded_text)

        total = len(all_sentences)
        confidence = len(grounded) / total if total > 0 else 1.0
        all_grounded = len(ungrounded) == 0

        return GroundingReport(
            grounded_text=grounded_text,
            total_sentences=total,
            grounded_sentences=grounded,
            ungrounded_sentences=ungrounded,
            confidence=confidence,
            grounded=all_grounded,
        )