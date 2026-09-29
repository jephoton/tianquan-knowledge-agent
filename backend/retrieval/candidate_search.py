"""Candidate search — inverted-index TF-IDF retrieval with result caching.

Given a natural-language query, returns the top-k candidate resources by
TF-IDF scoring against each resource's title + content. See ADR-0004 for
why this is used over vector embeddings for V1.

Design notes:
- This step deliberately OVER-FETCHES. Recall matters more than precision
  because the permission filter is the real gate (ADR-0002). A candidate
  surfaced here is not access — it is only a suggestion to be filtered.
- Scoring is deterministic (no randomness, no external model), which keeps
  the pipeline reproducible and easy to test against INV1/INV2.
- Title terms are weighted higher than body terms.
- An inverted index (token → resource_ids) avoids scanning all resources
  on every query; only resources that share at least one token with the
  query are scored.
- A small result cache keyed by (query_hash, index_size) avoids re-scoring
  identical queries. The cache is invalidated on reindex (index_size change
  is a proxy; a full cache key would include ACL versions, but candidates
  are pre-permission-filter anyway).
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field

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

_TITLE_WEIGHT = 3.0
_BODY_WEIGHT = 1.0

_MAX_CACHE_SIZE = 128


def tokenize(text: str) -> list[str]:
    """Lowercase, split on non-alphanumeric, and drop stopwords."""
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]


@dataclass
class ScoredCandidate:
    """A resource with its relevance score for a query."""

    resource: Resource
    entry: IndexEntry
    score: float


@dataclass
class _IndexEntry:
    """Pre-computed token data for a single resource in the index."""

    resource: Resource
    entry: IndexEntry
    title_tf: dict[str, int]  # term frequency in title
    body_tf: dict[str, int]   # term frequency in body


class CandidateSearch:
    """TF-IDF candidate search over an inverted index.

    The index is built lazily on the first search() call and rebuilt when
    the indexer's size changes (e.g. after a reindex). This keeps the
    inverted index in sync with the resource set without requiring the
    caller to manually rebuild.
    """

    def __init__(self, indexer: Indexer):
        self._indexer = indexer
        self._inverted: dict[str, set[str]] = {}  # token -> {resource_id}
        self._entries: dict[str, _IndexEntry] = {}  # resource_id -> data
        self._doc_count: int = 0
        self._index_size: int = -1  # forces build on first use
        self._cache: dict[str, list[ScoredCandidate]] = {}
        self._cache_order: list[str] = []

    def _build_index(self) -> None:
        """Build the inverted index and pre-compute term frequencies."""
        self._inverted.clear()
        self._entries.clear()
        all_entries = self._indexer.all_entries()
        self._doc_count = len(all_entries)

        for entry in all_entries:
            rid = entry.resource.resource_id
            title_tokens = tokenize(entry.resource.title)
            body_tokens = tokenize(entry.resource.content)

            title_tf: dict[str, int] = {}
            for t in title_tokens:
                title_tf[t] = title_tf.get(t, 0) + 1

            body_tf: dict[str, int] = {}
            for t in body_tokens:
                body_tf[t] = body_tf.get(t, 0) + 1

            self._entries[rid] = _IndexEntry(
                resource=entry.resource,
                entry=entry,
                title_tf=title_tf,
                body_tf=body_tf,
            )

            # Add to inverted index (unique tokens only — set deduplicates).
            for t in set(title_tokens) | set(body_tokens):
                self._inverted.setdefault(t, set()).add(rid)

        self._index_size = self._indexer.size()

    def _ensure_index(self) -> None:
        """Rebuild the index if it's stale or not yet built."""
        if self._index_size != self._indexer.size():
            self._build_index()
            self._cache.clear()
            self._cache_order.clear()

    def _idf(self, token: str) -> float:
        """Inverse document frequency for a token.

        Uses smoothed IDF: idf = ln(1 + N / (1 + df)).
        Rare terms get higher weight; common terms get lower weight.
        """
        df = len(self._inverted.get(token, set()))
        if df == 0:
            return 0.0
        return math.log(1 + self._doc_count / (1 + df))

    def _score(self, query_tokens: list[str]) -> list[ScoredCandidate]:
        """Score all resources that share at least one token with the query."""
        if not query_tokens:
            return []

        # Find candidate resource IDs via the inverted index.
        candidate_ids: set[str] = set()
        for token in query_tokens:
            candidate_ids.update(self._inverted.get(token, set()))

        # Unique query tokens for normalization.
        unique_query_tokens = set(query_tokens)

        scored: list[ScoredCandidate] = []
        for rid in candidate_ids:
            ie = self._entries[rid]
            score = 0.0

            for token in unique_query_tokens:
                idf = self._idf(token)
                if idf == 0.0:
                    continue

                title_hits = ie.title_tf.get(token, 0)
                body_hits = ie.body_tf.get(token, 0)

                if title_hits > 0:
                    score += _TITLE_WEIGHT * idf * title_hits
                if body_hits > 0:
                    # Only count body if not already in title (avoid double counting).
                    body_only = body_hits if title_hits == 0 else body_hits - title_hits
                    if body_only > 0:
                        score += _BODY_WEIGHT * idf * body_only

            if score > 0:
                # Normalize by query size for cross-query comparability.
                score /= len(unique_query_tokens)
                scored.append(
                    ScoredCandidate(
                        resource=ie.resource, entry=ie.entry, score=score,
                    )
                )

        scored.sort(key=lambda c: (-c.score, c.resource.resource_id))
        return scored

    def search(self, query: str, k: int = 10) -> list[ScoredCandidate]:
        """Return up to k candidates scored by TF-IDF relevance, highest first.

        Only resources with a positive score are returned. Ties are broken
        deterministically by resource_id so results are reproducible.

        Results are cached by (query, k); the cache is invalidated on reindex.
        """
        self._ensure_index()

        cache_key = hashlib.sha256(
            f"{query}::{k}".encode(),
        ).hexdigest()

        if cache_key in self._cache:
            return self._cache[cache_key]

        query_tokens = tokenize(query)
        scored = self._score(query_tokens)[:k]

        # LRU-like cache eviction.
        self._cache[cache_key] = scored
        self._cache_order.append(cache_key)
        if len(self._cache_order) > _MAX_CACHE_SIZE:
            oldest = self._cache_order.pop(0)
            self._cache.pop(oldest, None)

        return scored