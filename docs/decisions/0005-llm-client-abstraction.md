# ADR-0005: LLM client abstraction with ADP and offline fallback

<!-- Generated status reconciliation, 2026-10-11. -->

**Date:** 2026-09-28; provider resolution incorporated 2026-10-11.  
**Status:** Accepted — interface and concrete ADP provider implemented.

## Context

The answer agent needs a model to synthesize cited answers from assembled authorized context. The original provider decision was open while access to Tencent tooling was investigated; the WorkBuddy route was initially blocked. That blocker is historical: the ADP adapter and published agent are now working. CodeBuddy provides development usage evidence; it is not the runtime LLM adapter.

## Decision

Depend on `LLMClient.generate(prompt) -> str`, not a provider SDK in the answer agent. Use Tencent Cloud ADP for live generation when configured. Keep the deterministic extractive `StubLLMClient` for tests, offline operation and live-call failures. The backend selects the client using `ADP_APP_KEY`; the key belongs exclusively in backend configuration.

## Rationale

The permission gate precedes prompt construction and remains independent of the model provider. A small interface isolates SSE/TLS/provider concerns. Deterministic tests can exercise citations, denial/no-match behavior and audit sequencing without live network calls.

## Consequences

- `adp_client.py` implements the live adapter; `llm_client.py` contains the protocol/stub. Provider selection is no longer an open follow-up.
- Each ADP call creates a fresh conversation ([ADR-0007](0007-stateless-llm-calls.md)); do not attach an unfiltered agent knowledge base.
- Runtime generation errors fall back to the stub; `/health` reports key configuration, not per-answer provenance or provider availability.
- Citation validation and lexical grounding are implementation checks, not proof of generated truth. Known fallbacks/gaps are tracked in [current state](../current-state.md#known-boundaries-and-follow-ups).
- See the [completed integration reference](../history/adp-integration-reference.md) and [deployment plan](../deployment-plan.md).
