# Current State — VeriBrain

> **Last updated:** 2026-09-28

## Milestone

**M0 — Project bootstrap** → complete  
**M1 — Data model & mock sources** → complete  
**M2 — Policy engine** → complete  
**Next:** M3 — Permission-aware retrieval pipeline

## What exists

- [x] Git repository initialized.
- [x] `docs/` handoff layer: plan, architecture, current-state, decisions, dev-log.
- [x] `.kiro/steering/handoff-layer.md`: handoff-layer + commit-discipline rule.
- [x] Repo structure scaffolded.
- [x] **Core data model** (`backend/models.py`): Source, SensitivityLevel, Action, DecisionResult, User, ACL, Resource, Decision.
- [x] **Auth module**: `identity.py` (7 seed users) + `roles.py` (7 roles).
- [x] **Four mock connectors**: Confluence (5), Jira (6), Slack (5), GDrive (4) = 20 resources.
- [x] **Policy engine** (`backend/policy/`):
  - `policy_engine.py` — fail-closed `decide(user, resource, action) -> Decision`, plus `decide_many` and `filter_allowed` for the retrieval pipeline. Stateless: reads live ACL every call.
  - `permission_mapping.py` — source-specific rules (Confluence space/page, Jira project/issue-security, Slack channel-type, GDrive sharing) + sensitivity clearance matrix + role-based action permission.
  - `freshness_checker.py` — ACL version staleness detection (supports INV3), fail-closed on anomalies.
- [x] **55 tests passing**: M1 model/connectors (33) + M2 policy/mapping/freshness (22).
- [x] Miora added to tech stack.
- [x] Development log started with M0 screenshot.

## What's next

1. **M3 — Permission-aware retrieval pipeline**
   - `indexer.py` — index resources from all connectors with ACL snapshot.
   - `candidate_search.py` — retrieve candidate resource IDs for a query.
   - `permission_filter.py` — filter candidates through `PolicyEngine.filter_allowed` before the LLM.
   - `context_assembler.py` — assemble approved content into an LLM context window.
   - Integration tests proving LLM context contains only authorized documents (INV2).

## Blockers

None.

## Key decisions made

- See [decisions/](decisions/) for ADRs.