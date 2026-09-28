# Current State — VeriBrain

> **Last updated:** 2026-09-28 (M4 complete)

## Milestone

**M0 — Project bootstrap** → complete  
**M1 — Data model & mock sources** → complete  
**M2 — Policy engine** → complete  
**M3 — Permission-aware retrieval pipeline** → complete  
**M4 — TLA+ formal specification** → complete  
**Next:** M5 — Audit trail

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
- [x] **TLA+ formal spec** (`formal/`):
  - `access_control.tla` — query-lifecycle state machine (search → decide → retrieve → answer, with revocation) parameterised by a `BROKEN` flag.
  - `MC_safe` (BROKEN=FALSE) — TLC checks INV1/INV2/INV3/INV4/INV6/INV7, all hold (28 states, no error).
  - `MC_broken` (BROKEN=TRUE, filter-after-retrieval) — TLC finds an INV1 counterexample at depth 4 (over-fetched denied resource reaches the context). This is Demo 5.
  - INV5 (delegation/no-privilege-escalation) deferred to M11 stretch.
  - Verified runnable via bundled `tla2tools.jar` + Java 25; TLC output artifacts gitignored.
- [x] Miora added to tech stack.
- [x] Development log started with M0 screenshot.

## What's next

### M5 — Audit trail (planned)

**Goal:** a tamper-evident, hash-chained audit log with a query API and tests
for chain integrity and tamper detection (INV4 at the implementation level).

**Outline (module map already reserves `backend/audit/`):**

- `event_schema.py` — canonical `AuditEvent` (see architecture.md §4): event_id,
  timestamp, user_id, query_id, resource_id, action, decision, reason,
  acl_version, policy_version, previous_hash, event_hash.
- `hash_chain.py` — `event_hash = SHA256(previous_hash + canonical_json(event))`;
  append + verify-chain + detect-tamper.
- `audit_query.py` — filter events by user / resource / query / time window
  (backs Demo 4, the compliance-officer inquiry).
- Wire the retrieval pipeline's `FilterOutcome.decisions` into audit events so
  every allow/deny is recorded (closes the loop with INV4).
- Tests: chain verifies clean; mutating any event breaks verification;
  every decision produces exactly one event.

## Blockers

None.

## Key decisions made

- See [decisions/](decisions/) for ADRs.