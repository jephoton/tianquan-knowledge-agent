# ADR-0004: Keyword candidate search instead of vector embeddings for V1

**Date:** 2026-09-28  
**Status:** Superseded (M14 — hybrid TF-IDF + n-gram semantic search implemented)

## Context

M3 (the permission-aware retrieval pipeline) needs a candidate-search step
that, given a natural-language query, returns a set of candidate resources to
be filtered through the policy engine before reaching the LLM.

Two approaches:

1. **Vector embeddings + similarity search** — embed all resources and the
   query, retrieve by cosine similarity. The "standard" RAG approach.
2. **Keyword / token-overlap scoring** — score resources by overlap between
   query terms and resource title + content, retrieve the top matches.

The demo corpus is small (20 seed resources across four mock connectors) and
the project's value is in **permission-aware filtering and formal
verification**, not retrieval quality.

## Decision

Use **keyword / token-overlap candidate search** for V1, with an interface
that allows a vector-based implementation to be swapped in later.

## Rationale

- The corpus is 20 documents; keyword overlap is more than adequate and
  returns deterministic, explainable results — useful when demoing to judges.
- No external dependency (no embedding model, no vector store, no API key),
  which keeps the pipeline fast, offline, and reproducible in tests.
- The candidate-search step is deliberately allowed to **over-fetch**. Recall
  matters more than precision here, because the policy filter is the real gate
  (per ADR-0002, filtering happens pre-LLM). A cheap keyword search that
  over-fetches, then a strict policy filter, is exactly the right shape.
- Determinism makes the pipeline easy to test against INV1/INV2.

## Consequences

- Candidate search is defined behind a small interface (`search(query, k)`),
  so a vector implementation can replace it without touching the policy
  filter, context assembler, or audit layers.
- Retrieval quality is basic (no semantic matching, no synonyms). Acceptable
  for the demo corpus; flagged as a stretch upgrade if time permits.
- The permission filter must re-fetch the **live** ACL from the connector at
  query time (not the indexed snapshot), so that candidate over-fetching can
  never leak revoked content. Freshness checking (M2) backs this.

## Update (M14, 2026-09-29)

The stretch upgrade has been implemented. Candidate search now uses:
- **Inverted index** (token → resource_ids) for O(query_tokens) lookup
- **TF-IDF scoring** for term-rarity-aware ranking
- **Character n-gram similarity** (bigrams + trigrams) for semantic fuzzy
  matching — "db" matches "database", "migrate" matches "migration"
- **Connector-level source filtering** — query mentioning "jira" skips
  non-Jira connectors
- **Parallel connector polling** — ThreadPoolExecutor for `list_resources()`
- **Result caching** — LRU cache keyed by (query, k), invalidated on reindex

No external embedding model or vector store is needed — the n-gram approach
provides semantic matching while remaining deterministic and offline.
