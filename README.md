# Tianquan 天权

> **Auditable AI answers that never overstep access rights.**

Tianquan (天权 — "heaven's authority") is a permission-aware enterprise knowledge demo across mock Confluence, Jira, Slack and Google Drive sources. Its access-control design is specified and model-checked in TLA+.

Built for the **Tencent Cloud AI CAN DO IT Singapore Hackathon 2026 — Track 4: FinTech (Aspire)**.

## Quick links

- **Live demo:** **https://tianquan.vercel.app** — pick a persona top-right. The backend is on Render's free tier: the first visit after ~15 idle minutes takes 30–60 s to wake, and the demo state resets then.
- **CodeBuddy usage evidence:** [development log with CodeBuddy screenshots](docs/dev-log/dev-log.md#codebuddy-usage-evidence)
- **Live ADP agent:** [Try Tianquan on Tencent Cloud ADP](https://adp.tencentcloud.com/webim_exp/#/chat/ULzqcG) — direct model chat; it does not run the full application's permission/audit pipeline.
- [Plan & Roadmap](docs/plan.md) — scope, milestones and submission checklist
- [Architecture](docs/architecture.md) — diagram ([PNG](docs/architecture.png)), trust boundaries, module map
- [Current State](docs/current-state.md) — what exists now, what's next
- [Demo Runbook](docs/demo-runbook.md) — step-by-step demo scenarios · [Demo Script](docs/demo-script.md) — concise demo pointers with optional extensions
- [Deployment plan](docs/superpowers/plans/2026-10-11-cloud-demo-deployment.md) — Vercel frontend + Render backend (deployed 2026-10-11)
- [Project description](docs/project-description.md) — blurb, overview, scenario insights, solution design, business value
- [Decisions](docs/decisions/) — architecture decision records (ADRs)

## What this is

A permission-aware Internal Brain that:

- Unifies knowledge across four enterprise platforms.
- Filters documents **before** they reach the LLM based on the asker's permissions.
- Handles live permission revocation without serving stale-permitted content.
- Records every retrieval, denial, and answer in a tamper-evident audit trail.
- Backs the access-control model with a TLA+ specification and model-checked safety invariants.

## The differentiator

Retrieval must enforce access rights before assembling LLM context. Tianquan's core constraint is:

> **The LLM cannot leak what it never receives.**

A Python policy engine enforces authorization; TLA+ model-checks six safety invariants of an abstract finite design. Tests check corresponding implementation behavior. This is not a proof of the full Python application; [current state](docs/current-state.md#known-boundaries-and-follow-ups) records its limits.

## Tech stack

| Layer        | Technology            |
|--------------|----------------------|
| Backend      | Python / FastAPI      |
| Frontend     | Static HTML/JS (Miora-generated), vendored Tailwind |
| Formal model | TLA+                  |
| Audit log    | Hash-chained JSONL    |
| LLM          | Tencent Cloud ADP (offline extractive fallback) |
| UI design    | Miora (dashboard design, cover image) |
| Dev tool     | CodeBuddy (planning and core build) |

Built with **Tencent Cloud**: CodeBuddy for development, **ADP** for live
LLM answers (called with only the permission-filtered context), and **Miora**
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

2. Run the tests (292 passing on 2026-10-11). If a demo is running, use the
   [isolated audit-path command](tests/README.md#run) to protect its log:

   ```powershell
   python -m pytest -q
   ```

3. Start the backend API:

   ```powershell
   python -m uvicorn backend.api.app:app --port 8000 --workers 1
   ```

   Interactive API docs at `http://localhost:8000/docs`.

4. Start the frontend (static, no build step) from `frontend/`:

   ```powershell
   python -m http.server 5500
   ```

   Open `http://127.0.0.1:5500/`. The UI needs no internet access; set
   `ADP_APP_KEY` in `.env` to answer with the live Tencent Cloud ADP agent
   (without it, or offline, answers come from the extractive fallback).

Hosted at https://tianquan.vercel.app (Vercel static UI) with the API on Render (`https://tianquan-api.onrender.com`, one free-tier instance) — see the [deployment plan](docs/superpowers/plans/2026-10-11-cloud-demo-deployment.md).
Run one backend worker/instance. Restart resets ACL mutations/uploads and clears
the audit log; local disk is not restart persistence.

To walk through the demo scenarios, follow the
[demo runbook](docs/demo-runbook.md).

See [current-state.md](docs/current-state.md) for build progress and
[docs/](docs/) for the full handoff layer.