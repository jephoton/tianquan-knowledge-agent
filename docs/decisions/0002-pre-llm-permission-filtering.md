# ADR-0002: Pre-LLM permission filtering over post-generation filtering

**Date:** 2026-09-27  
**Status:** Accepted

## Context

The Aspire challenge explicitly requires that "the retrieval pipeline must filter candidate documents before they reach the LLM, so the model never even sees content the user is not allowed to see."

Two architectural approaches:

1. **Pre-LLM filtering:** Filter candidates through the policy engine before assembling LLM context. The LLM only receives authorized content.
2. **Post-generation filtering:** Let the LLM see all content, then filter the generated answer.

## Decision

Use **pre-LLM filtering** exclusively.

## Rationale

- Post-generation filtering cannot guarantee the LLM doesn't leak restricted content through paraphrasing or confabulation.
- The challenge statement explicitly mandates pre-LLM filtering.
- This gives a clean, judge-understandable claim: "The LLM cannot leak what it never receives."
- Pre-filtering is simpler to formally verify (INV2: `LLMSeesOnlyRetrievedContent`).

## Consequences

- The policy engine is on the hot path of every retrieval.
- Candidate search must be efficient enough to over-fetch, then filter.
- The LLM context window may be smaller than available content (only authorized subset).