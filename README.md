# VeriBrain

> **Auditable AI answers that never overstep access rights.**

VeriBrain is a formally constrained enterprise knowledge agent for permission-safe AI retrieval across Confluence, Jira, Slack, and Google Drive.

Built for the **Tencent Cloud AI CAN DO IT Singapore Hackathon 2026 — Track 4: FinTech (Aspire)**.

## Quick links

- [Plan & Roadmap](docs/plan.md) — source of truth, scope, milestones
- [Architecture](docs/architecture.md) — system design, trust boundaries, module map
- [Current State](docs/current-state.md) — what exists now, what's next
- [Decisions](docs/decisions/) — architecture decision records (ADRs)

## What this is

A permission-aware Internal Brain that:

- Unifies knowledge across four enterprise platforms.
- Filters documents **before** they reach the LLM based on the asker's permissions.
- Handles live permission revocation without serving stale-permitted content.
- Records every retrieval, denial, and answer in a tamper-evident audit trail.
- Backs the access-control model with a TLA+ specification and model-checked safety invariants.

## The differentiator

Most "AI over your data" demos retrieve documents into LLM context with no regard for who is asking. VeriBrain's core constraint is:

> **The LLM cannot leak what it never receives.**

Every authorization decision is checked against a formally specified RBAC + delegation model, and every decision is auditable.

## Tech stack

| Layer        | Technology            |
|--------------|----------------------|
| Backend      | Python / FastAPI      |
| Frontend     | React + TypeScript    |
| Formal model | TLA+                  |
| Audit log    | Hash-chained JSON     |
| LLM          | Tencent Cloud LLM via WorkBuddy / ADP |

## Repository structure

```
frontend/          # React + TypeScript UI
backend/
    api/           # FastAPI routes
    connectors/    # Mock Confluence/Jira/Slack/GDrive
    auth/          # Identity, roles, sessions
    policy/        # Policy engine, permission mapping, delegation
    retrieval/     # Indexer, candidate search, permission filter, context assembler
    agents/        # Orchestrator, answer agent, optional action agent
    audit/         # Event schema, hash chain, audit query
formal/            # TLA+ specification and config
tests/             # Integration and property tests
docs/              # Handoff layer: plan, architecture, current-state, decisions
```

## Getting started

> Setup instructions will be added once scaffolding is complete. See [current-state.md](docs/current-state.md) for progress.