# Current State — VeriBrain

> **Last updated:** 2026-09-27

## Milestone

**M0 — Project bootstrap** → ✅ complete  
**Next:** M1 — Data model & mock sources

## What exists

- [x] Git repository initialized.
- [x] `.gitignore` created.
- [x] `README.md` created.
- [x] `docs/plan.md` — source of truth with roadmap and submission deliverables.
- [x] `docs/architecture.md` — system design, trust boundaries, module map.
- [x] `docs/current-state.md` — this file.
- [x] `docs/decisions/` — 3 ADRs (TLA+, pre-LLM filtering, mock connectors).
- [x] Repo structure scaffolded (`frontend/`, `backend/`, `formal/`, `tests/`).
- [x] Initial commit pushed.
- [x] Miora added to tech stack for frontend UI generation.

## What's next

1. **M1 — Data model & mock sources**
   - Define resource data model (source, resource_id, title, content, ACL, sensitivity).
   - Build mock connectors for Confluence, Jira, Slack, Google Drive.
   - Create seed data with varied ACLs across all four platforms.
   - Include scenarios for all 5 demos (authorized access, denial, revocation, audit, formal verification).

## Blockers

None.

## Key decisions made

- See [decisions/](decisions/) for ADRs.