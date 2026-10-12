# ADP Integration — Completed Reference

<!-- Generated reconciliation, 2026-10-11. Original setup plan preserved in ../history/adp-setup-plan.md. -->

The adapter and published ADP agent already exist; registration, publishing and response-format discovery are not pending implementation tasks. The [original setup plan](../history/adp-setup-plan.md) is historical. Cloud application hosting remains [planned](../deployment-plan.md).

## Implemented flow

`backend/agents/adp_client.py` implements `LLMClient.generate(prompt) -> str`, sends the assembled question/context to ADP and parses UTF-8 SSE responses. Every call starts a fresh conversation ([ADR-0007](../decisions/0007-stateless-llm-calls.md)); context must not carry between personas. The policy filter runs before prompt construction. Keep the ADP agent free of an attached knowledge base so additional source data does not bypass that filter.

`backend/api/state.py` selects ADP when `ADP_APP_KEY` is present and the client can be initialized; otherwise it selects the extractive stub. `Orchestrator.handle()` also falls back to the stub if live answer generation raises an exception. Empty authorized context returns the canonical no-access message without calling ADP.

## Configuration and verification

Store `ADP_APP_KEY` only in the backend environment or ignored local `.env`. Use the run commands in the [backend README](../../backend/README.md). `/health` returns `llm: adp` when a key is configured; it does not test a provider connection or distinguish a fallback answer. Verify live usage through an allowed request and provider-side evidence rather than health alone. Never copy keys or secret-bearing logs into documentation or frontend assets.

The test suite forces the stub; adapter tests mock HTTP. Prior live API checks confirmed Bob Q3 denial, Charlie Q3 citations/preview/export and missing-Q5 parity. A new hosted deployment must repeat those checks; local evidence is not cloud verification.

## Remaining boundaries

Citation validation checks marker membership, not factual entailment. Grounding uses lexical/entity heuristics; if all sentences are rejected, the orchestrator restores the original citation-validated text for both stub and live output. It does not produce a citation-only replacement. The known grounding, ACL and concurrency gaps are documented in [current state](../current-state.md#known-boundaries-and-follow-ups).

The [published ADP experience](https://adp.tencentcloud.com/webim_exp/#/chat/ULzqcG) is direct model chat. It does not run Tianquan's API identity, permission, source-preview/export or audit controls and is not the full app demo URL.
