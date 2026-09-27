# Current State — VeriBrain

> **Last updated:** 2026-09-27

## Milestone

**M0 — Project bootstrap** → complete  
**M1 — Data model & mock sources** → complete  
**Next:** M2 — Policy engine

## What exists

- [x] Git repository initialized.
- [x] `docs/` handoff layer: plan, architecture, current-state, decisions, dev-log.
- [x] Repo structure scaffolded.
- [x] **Core data model** (`backend/models.py`): Source, SensitivityLevel, Action, DecisionResult, User, ACL, Resource, Decision.
- [x] **Auth module**: `identity.py` (7 seed users) + `roles.py` (7 roles).
- [x] **Four mock connectors**: Confluence (5), Jira (6), Slack (5), GDrive (4) = 20 resources.
- [x] **33 tests passing**: model, users, roles, all connectors, cross-source.
- [x] Miora added to tech stack.
- [x] Development log started with M0 screenshot.

## What's next

1. **M2 — Policy engine**
   - Authorization decision function: `decide(user, resource, action) -> Decision`.
   - Source-specific permission mapping to common model.
   - ACL versioning support.
   - Unit tests for positive and negative cases.

## Blockers

None.

## Key decisions made

- See [decisions/](decisions/) for ADRs.