# ADR-0005: LLM client behind an interface; provider decision deferred

**Date:** 2026-09-28  
**Status:** Partially accepted — interface **Accepted**; concrete provider **Open**

## Context

M6 (the answer agent) needs to call an LLM to generate grounded, cited answers
from the assembled context. Two questions arose:

1. **Architecture:** should the answer agent call a provider SDK directly, or
   talk to an abstraction?
2. **Provider:** Tencent Cloud LLM via WorkBuddy/ADP (the hackathon-required
   surface) vs a free/open-source model (e.g. local Ollama) for development?

Two hard constraints frame the provider question:

- The track requires building on Tencent Cloud AI; WorkBuddy/ADP is the named
  LLM surface, and CodeBuddy/WorkBuddy usage proof is a **required** M13
  submission deliverable. A free model as the *only* path risks the submission.
- The provider access path (WorkBuddy vs ADP, credentials) is **not yet
  confirmed** by the team.

A key property de-risks this: the permission-safety guarantee (INV1/INV2) lives
entirely in the retrieval pipeline. The LLM only ever receives already-filtered
context, so it is a swappable component behind a trust boundary (architecture.md
§2, boundary 4). Nothing about safety depends on which model is used.

## Decision

**Accepted now:** the answer agent depends on an `LLMClient` interface
(a minimal `generate(prompt, context) -> str` protocol), never a concrete SDK.
M6 is built and tested against a **deterministic stub** implementation so all
answer-agent logic (grounding, citation validation, no-metadata-leak, and the
end-to-end query→retrieval→answer→audit path) runs offline and reproducibly.

**Deferred (Open):** which concrete `LLMClient` backs the demo. Candidates:

| Option | Role | Notes |
|--------|------|-------|
| Tencent Cloud LLM (WorkBuddy/ADP) | **demo / submission path** | Required by the track. Needs credentials — TBC. |
| Local open-source (e.g. Ollama) | optional dev adapter | Realistic offline dev; not submission-valid on its own. |
| Deterministic stub | tests / CI | Canned grounded answers from context; always available. |

This ADR will be updated to fully Accepted once the provider access path is
confirmed.

## Rationale

- The interface is the actual debt-avoiding move: it decouples every downstream
  milestone from the provider choice, so deferring the provider costs nothing.
- A stub keeps tests fast, offline, and deterministic — important because the
  invariants (INV6 no-unauthorized-citation, INV7 no-metadata-leak) must be
  asserted reliably, not against a nondeterministic model.
- Keeps the WorkBuddy/ADP requirement firmly in scope (it's the intended demo
  path) without blocking implementation on credentials.

## Consequences

- One small module (`backend/agents/llm_client.py`) defines the protocol and
  the stub; provider adapters are added later without touching the answer agent.
- M6 can be completed and fully tested now; the demo path is a config swap.
- Open follow-up (blocks the *live demo*, not implementation): confirm
  WorkBuddy vs ADP + credentials, then add the Tencent adapter and update this
  ADR to Accepted.
