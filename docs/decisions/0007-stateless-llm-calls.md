# ADR-0007: Every LLM call is stateless (fresh ADP conversation per query)

**Date:** 2026-10-11  
**Status:** Accepted

## Context

The API process holds one `ADPClient`, shared by every user's queries. The
client created one ADP `ConversationId` at construction and reused it for every
call. ADP keeps conversation history per `ConversationId`, so each prompt was
answered with memory of earlier prompts — including other users' authorized
context.

Observed live: after alice's migration query, charlie's payment-outage answer
contained sentences that charlie's own (permission-filtered) context did not
support. The grounding checker removed them, but the model should never have
had them. This violates INV2 / TB4: the LLM must see only the current asker's
filtered context.

## Decision

Generate a new `ConversationId` for every `generate()` call. Tianquan does not
use multi-turn chat; each query carries its complete authorized context.

## Rationale

- Statelessness makes TB4 hold by construction rather than relying on the
  grounding checker as a backstop.
- The answer agent already sends the full context with each prompt, so no
  answer quality is lost.

## Consequences

- A regression test asserts two consecutive calls use different conversation
  ids.
- If multi-turn chat is added later, conversation state must be keyed per user
  **and** per authorization state, never shared across users.
