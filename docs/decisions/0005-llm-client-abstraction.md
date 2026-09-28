# ADR-0005: Abstract the LLM behind an `LLMClient` interface; stub for dev, WorkBuddy for demo

**Date:** 2026-09-28  
**Status:** Accepted

## Context

M6 (the answer agent) needs to call a large language model to generate a
grounded, cited answer from the assembled context. The hackathon track
requires building on Tencent Cloud AI, and the LLM is specified as "Tencent
Cloud LLM via WorkBuddy / ADP" (see plan.md §6). CodeBuddy/WorkBuddy usage
proof is a required M13 submission deliverable.

Constraints discovered during planning:

- The **WorkBuddy API is paywalled** — it requires a Pro upgrade we do not
  currently have. We cannot call it from code today.
- Development and tests must run offline and deterministically.

Critically: the permission-safety guarantees (INV1 RetrievedOnlyIfAuthorized,
INV2 LLMSeesOnlyRetrievedContent) live entirely in the retrieval pipeline
(ADR-0002). The LLM only ever receives already-filtered context. It is a leaf
component — "which LLM" is a deployment decision, not an architecture decision.

## Decision

Introduce an **`LLMClient` interface** that the answer agent depends on. Ship:

1. `LLMClient` protocol — `generate(system, prompt, context) -> str`.
2. `StubLLMClient` — deterministic, offline; grounds its answer in the
   supplied context. **Default for all development and tests.**
3. `TencentLLMClient` — WorkBuddy/ADP adapter. Call shape implemented; not
   required to run until Pro access is available. Swapped in via config.
4. (Optional) a local open-source adapter (e.g. Ollama) for realistic offline
   dev, if we want a real model without credentials.

The concrete client is selected by configuration, not code.

## Rationale

- **No blocking:** M6 is fully built and verified with the stub; we are not
  blocked on the WorkBuddy Pro paywall.
- **No debt:** the interface is the deliverable that prevents rework. When
  WorkBuddy (or any model) becomes available, it is wired in via config with
  zero changes to the answer agent.
- **Requirement stays in scope:** WorkBuddy/ADP remains the documented demo
  path; the abstraction keeps the Tencent integration a drop-in.
- **Safety is unaffected:** permission filtering is pre-LLM, so the choice of
  model cannot affect INV1/INV2. Tests assert safety independent of the client.
- **Deterministic tests:** the stub makes answer-agent behavior (citation
  validation, no-metadata-leak on empty context) reproducible.

## Consequences

- The answer agent must never import a concrete LLM SDK directly — only the
  `LLMClient` interface.
- The live WorkBuddy path is unverified until Pro access is obtained; this is
  tracked as a blocker in current-state.md. Fallbacks if Pro never lands:
  CodeBuddy (already the documented dev tool, satisfies usage-proof) and/or a
  local model for the live demo.
- Citation grounding and the no-leak denial message are enforced in the agent
  regardless of client, so swapping models cannot regress those behaviors.
