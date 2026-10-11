# Tianquan 天权

> **Auditable AI answers that never overstep access rights.**

Tianquan (天权 — "heaven's authority") is a formally constrained enterprise knowledge agent for permission-safe AI retrieval across Confluence, Jira, Slack, and Google Drive.

Built for the **Tencent Cloud AI CAN DO IT Singapore Hackathon 2026 — Track 4: FinTech (Aspire)**.

## Quick links

- **Live ADP agent:** [Try Tianquan on Tencent Cloud ADP](https://adp.tencentcloud.com/webim_exp/#/chat/ULzqcG) — the agent name and welcome message are confirmed visible.
- [Plan & Roadmap](docs/plan.md) — source of truth, scope, milestones
- [Architecture](docs/architecture.md) — diagram ([PNG](docs/architecture.png)), trust boundaries, module map
- [Current State](docs/current-state.md) — what exists now, what's next
- [Demo Runbook](docs/demo-runbook.md) — step-by-step demo scenarios · [Demo Script](docs/demo-script.md) — concise demo pointers with optional extensions
- [Decisions](docs/decisions/) — architecture decision records (ADRs)

## What this is

A permission-aware Internal Brain that:

- Unifies knowledge across four enterprise platforms.
- Filters documents **before** they reach the LLM based on the asker's permissions.
- Handles live permission revocation without serving stale-permitted content.
- Records every retrieval, denial, and answer in a tamper-evident audit trail.
- Backs the access-control model with a TLA+ specification and model-checked safety invariants.

## The differentiator

Most "AI over your data" demos retrieve documents into LLM context with no regard for who is asking. Tianquan's core constraint is:

> **The LLM cannot leak what it never receives.**

Every authorization decision is checked against a formally specified access-control model, and every decision is auditable.

## Tech stack

| Layer        | Technology            |
|--------------|----------------------|
| Backend      | Python / FastAPI      |
| Frontend     | Static HTML/JS (Miora-generated), vendored Tailwind |
| Formal model | TLA+                  |
| Audit log    | Hash-chained JSON     |
| LLM          | Tencent Cloud ADP (offline extractive fallback) |
| UI design    | Miora (dashboard design, cover image) |
| Dev tool     | CodeBuddy (planning and core build) |

Built with **Tencent Cloud**: CodeBuddy for development, **ADP** for every
LLM answer (called with only the permission-filtered context), and **Miora**
for the UI design and cover image — see
[project-description.md](docs/project-description.md#tencent-cloud-tools-used).

## Repository structure

```
frontend/          # Miora-generated static UI (no build step); vendor/ = pinned Tailwind
backend/
    api/           # FastAPI routes
    connectors/    # Mock Confluence/Jira/Slack/GDrive (+ runtime upload connector)
    auth/          # Identity, roles
    policy/        # Policy engine, permission mapping, revoke/grant, permissions inspector
    retrieval/     # Indexer, candidate search, permission filter, context assembler
    agents/        # Orchestrator, ADP client, answer agent, grounding checker, injection scanner
    audit/         # Event schema, hash chain, audit query, plain-English audit search
    seed/          # Seed documents
formal/            # TLA+ specification and config
tests/             # Integration and property tests
docs/              # Handoff layer: plan, architecture, current-state, decisions
```

## Getting started

**Prerequisites:** Python 3.11+ (uses `X | Y` type syntax). Java 17+ only if you
want to run the TLA+ model checker.

1. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

2. Run the tests (275 tests):

   ```powershell
   python -m pytest -q
   ```

3. Start the backend API:

   ```powershell
   uvicorn backend.api.app:app --port 8000
   ```

   Interactive API docs at `http://localhost:8000/docs`.

4. Start the frontend (static, no build step) from `frontend/`:

   ```powershell
   python -m http.server 5500
   ```

   Open `http://127.0.0.1:5500/`. The UI needs no internet access; set
   `ADP_APP_KEY` in `.env` to answer with the live Tencent Cloud ADP agent
   (without it, or offline, answers come from the extractive fallback).

To walk through the demo scenarios, follow the
[demo runbook](docs/demo-runbook.md).

See [current-state.md](docs/current-state.md) for build progress and
[docs/](docs/) for the full handoff layer.