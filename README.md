# Tianquan 天权

> **Auditable AI answers that never overstep access rights.**

Tianquan (天权 — "heaven's authority") is a formally constrained enterprise knowledge agent for permission-safe AI retrieval across Confluence, Jira, Slack, and Google Drive.

Built for the **Tencent Cloud AI CAN DO IT Singapore Hackathon 2026 — Track 4: FinTech (Aspire)**.

## Quick links

- [Plan & Roadmap](docs/plan.md) — source of truth, scope, milestones
- [Architecture](docs/architecture.md) — system design, trust boundaries, module map
- [Current State](docs/current-state.md) — what exists now, what's next
- [Demo Runbook](docs/demo-runbook.md) — step-by-step script for the 5 demos
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

Every authorization decision is checked against a formally specified RBAC + delegation model, and every decision is auditable.

## Tech stack

| Layer        | Technology            |
|--------------|----------------------|
| Backend      | Python / FastAPI      |
| Frontend     | Static HTML/JS (Miora-generated) |
| Formal model | TLA+                  |
| Audit log    | Hash-chained JSON     |
| LLM          | Tencent Cloud LLM via WorkBuddy / ADP |

## Repository structure

```
frontend/          # Miora-generated static UI (no build step)
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

**Prerequisites:** Python 3.11+ (uses `X | Y` type syntax). Java 17+ only if you
want to run the TLA+ model checker.

1. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

2. Run the tests (138 tests):

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

   Open `http://localhost:5500/`.

To walk through the demo scenarios, follow the
[demo runbook](docs/demo-runbook.md).

See [current-state.md](docs/current-state.md) for build progress and
[docs/](docs/) for the full handoff layer.