# Current State — VeriBrain

> **Last updated:** 2026-09-28 (M3 planned)

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

### M3 — Permission-aware retrieval pipeline (planned)

**Goal:** query → candidate search → policy filter → context assembler, where
the LLM context provably contains only authorized documents (INV1, INV2).

**Design decision:** keyword/token-overlap candidate search for V1
(see [ADR-0004](decisions/0004-keyword-candidate-search-for-v1.md)). The
filter re-fetches the **live** ACL from connectors at query time so
over-fetched candidates cannot leak revoked content.

**Task breakdown (build in this order):**

1. `retrieval/indexer.py` — `Indexer` pulls `list_resources()` from all four
   connectors, stores each `Resource` keyed by `resource_id` with an
   `indexed_acl_version` snapshot. Methods: `reindex()`, `all_resources()`,
   `get(resource_id)`.
2. `retrieval/candidate_search.py` — `CandidateSearch.search(query, k)` scores
   indexed resources by query-term overlap on title + content, returns the top
   `k` candidates (over-fetch). Deterministic, no external deps.
3. `retrieval/permission_filter.py` — `PermissionFilter.filter(user, candidates,
   action)` re-fetches the live ACL per candidate from its connector, runs
   `PolicyEngine.filter_allowed`, flags stale indexed entries via
   `freshness_checker`, returns `(allowed_resources, decisions)`. Denied
   resources are dropped entirely — the LLM never sees them.
4. `retrieval/context_assembler.py` — `ContextAssembler.assemble(allowed,
   max_chars)` concatenates approved content into a bounded context window with
   citation markers; returns the context string plus the list of citable
   resource IDs (for later INV6 citation validation).
5. `retrieval/pipeline.py` (or extend orchestrator later) — wire the four steps:
   `search → filter → assemble`.
6. **Integration tests** (`tests/test_m3_retrieval.py`):
   - INV1/INV2: for each seed user, the assembled context contains no resource
     the policy engine would deny.
   - Over-fetch safety: a candidate that matches by keyword but is denied by
     policy never appears in the context.
   - Revocation: after `update_acl` revokes access, the next pipeline run
     excludes that resource (ties M2 freshness to M3).
   - Contractor (Bob) gets strictly fewer/no restricted docs vs engineer (Alice)
     for the same query.

**Exit criteria (from plan.md):** candidate search → policy filter → context
assembler working; LLM never sees denied content; integration tests prove the
context contains only authorized documents.

## Blockers

None.

## Key decisions made

- See [decisions/](decisions/) for ADRs.