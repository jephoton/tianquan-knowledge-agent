"""Candidate search — keyword / token-overlap retrieval.

Given a natural-language query, returns the top-k candidate resources by
term overlap against each resource's title + content. See ADR-0004 for why
this is used over vector embeddings for V1.

Design notes:
- This step deliberately OVER-FETCHES. Recall matters more than precision
  because the permission filter is the real gate (ADR-0002). A candidate
  surfaced here is not access — it is only a suggestion to be filtered.
- Scoring is deterministic (no randomness, no external model), which keeps
  the pipeline reproducible and easy to test against INV1/INV2.
- Title terms are weighted higher than body terms.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from backend.models import Resource
from backend.retrieval.indexer import IndexEntry, Indexer

# Common English stopwords to drop from queries and documents so that
# scoring reflects meaningful term overlap rather than filler words.
_STOPWORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
    "have", "how", "i", "in", "is", "it", "its", "of", "on", "or", "that",
    "the", "there", "they", "this", "to", "was", "were", "what", "when",
    "where", "which", "who", "will", "with", "were", "do", "does", "did",
    "me", "my", "we", "you", "your", "about", "into", "over", "last",
})

_TOKEN_RE = re.compile(r"[a-z0-9]+")

_TITLE_WEIGHT = 3
_BODY_WEIGHT = 1


def tokenize(text: str) -> list[str]:
    """Lowercase, split on non-alphanumeric, and drop stopwords."""
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]


@dataclass
class ScoredCandidate:
    """A resource with its relevance score for a query."""

    resource: Resource
    entry: IndexEntry
    score: float


class CandidateSearch:
    """Keyword/token-overlap candidate search over an index."""

    def __init__(self, indexer: Indexer):
        self._indexer = indexer

    def _score(self, query_tokens: set[str], resource: Resource) -> float:
        """Score a resource by weighted overlap with the query tokens.

        Title matches are weighted higher than body matches. The score is
        normalized by query size so it is comparable across queries.
        """
        if not query_tokens:
            return 0.0

        title_tokens = set(tokenize(resource.title))
        body_tokens = set(tokenize(resource.content))

        title_hits = query_tokens & title_tokens
        body_hits = (query_tokens & body_tokens) - title_hits

        raw = _TITLE_WEIGHT * len(title_hits) + _BODY_WEIGHT * len(body_hits)
        return raw / len(query_tokens)

    def search(self, query: str, k: int = 10) -> list[ScoredCandidate]:
        """Return up to k candidates scored by relevance, highest first.

        Only resources with a positive score are returned. Ties are broken
        deterministically by resource_id so results are reproducible.
        """
        query_tokens = set(tokenize(query))
        scored: list[ScoredCandidate] = []
        for entry in self._indexer.all_entries():
            score = self._score(query_tokens, entry.resource)
            if score > 0:
                scored.append(
                    ScoredCandidate(
                        resource=entry.resource, entry=entry, score=score,
                    )
                )

        scored.sort(key=lambda c: (-c.score, c.resource.resource_id))
        return scored[:k]
