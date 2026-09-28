# Current State — VeriBrain

> **Last updated:** 2026-09-28 (M3 complete)

## Milestone

**M0 — Project bootstrap** → complete  
**M1 — Data model & mock sources** → complete  
**M2 — Policy engine** → complete  
**M3 — Permission-aware retrieval pipeline** → complete  
**Next:** M4 — TLA+ formal specification

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
- [x] **Retrieval pipeline** (`backend/retrieval/`):
  - `indexer.py` — `Indexer` snapshots all connector resources with `indexed_acl_version`; authorization is never decided from the index.
  - `candidate_search.py` — `CandidateSearch.search(query, k)`, deterministic keyword/token-overlap scoring (title-weighted), over-fetches (ADR-0004).
  - `permission_filter.py` — `PermissionFilter.filter` re-fetches **live** ACLs per candidate, runs `PolicyEngine`, records freshness, drops denied resources (INV1/INV2). Returns allowed set + all decisions for audit.
  - `context_assembler.py` — `ContextAssembler.assemble` builds a bounded, citation-marked context; exposes `is_authorized_citation` for later INV6 validation.
  - `pipeline.py` — `RetrievalPipeline.run(user, query)` wires search → filter → assemble.
- [x] **75 tests passing**: M1 (33) + M2 (22) + M3 retrieval (20).
- [x] Miora added to tech stack.
- [x] Development log started with M0 screenshot.

## What's next

### M4 — TLA+ formal specification (planned)

**Goal:** `formal/access_control.tla` modeling the access-control state machine
with all 7 invariants; TLC model-checks them; a deliberately broken variant
(filter-after-retrieval) yields a counterexample for the demo (Demo 5).

**Outline:**

- Model entities: Users, Roles, Resources, ACLs (with version), Queries,
  Retrievals, the LLM context set, AuditEvents, Revocations.
- Actions: submit query, search candidates, policy-decide, retrieve into
  context, revoke permission, emit audit event.
- Invariants to encode: INV1 RetrievedOnlyIfAuthorized, INV2
  LLMSeesOnlyRetrievedContent, INV3 RevokedAccessNotReusable, INV4
  EveryDecisionAudited, INV6 NoUnauthorizedCitation, INV7 NoMetadataLeakOnDeny
  (INV5 delegation is a stretch, M11).
- Broken variant: reorder so retrieval happens before the policy decision;
  show TLC finds a state violating INV2.
- Keep the model small (2-3 users, 2-3 resources, 1 revocation) so TLC
  finishes fast and the state graph is explainable to judges.

**Note:** the implementation already mirrors these invariants — M3 tests cover
INV1/INV2/INV3 at the code level, so the TLA+ spec and the Python tests should
tell the same story.

## Blockers

None.

## Key decisions made

- See [decisions/](decisions/) for ADRs.