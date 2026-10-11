# ADR-0006: A named platform boosts ranking; it never filters sources out

**Date:** 2026-10-11  
**Status:** Accepted

## Context

Candidate search had a "connector filter": if the question contained a source
keyword (`slack`, `jira`, `confluence`, but also generic words like `page`,
`issue`, `docs`, `document`, `file`, `message`), only that one source was
searched.

That broke the challenge's headline scenario. The demo question — *"What is the
status of the database migration and were there blockers raised in Slack?"* —
returned a single Slack thread: no Jira tickets, no Confluence plan, and no
denials to show. The handbook's own CTO question (*"…from last sprint's Slack
threads and link the Confluence decision doc"*) searched Slack only and never
found the Confluence doc it asks for.

## Decision

A platform named in the question multiplies the score of that platform's
resources by `_SOURCE_BOOST` (2.0). Every source is always searched, and
several platforms can be named at once.

## Rationale

- Cross-platform answers are the point of the system; "in Slack" narrows
  emphasis, not scope.
- Candidate search is pre-authorization and deliberately over-fetches
  (ADR-0002). Recall matters more than precision; the permission filter is the
  real gate.
- 2.0 is enough for an explicit mention ("jira migration ticket") to put that
  source first in this corpus; 1.5 was not.

## Consequences

- The demo question again draws on Jira, Slack, Confluence and Drive, with the
  restricted breach report and SEC ticket denied before the LLM.
- Regression tests cover the demo question and the handbook's two-source
  question.
