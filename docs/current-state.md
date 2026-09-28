# Current State — VeriBrain

> **Last updated:** 2026-09-28 (M5 complete)

## Milestone

**M0 — Project bootstrap** → complete  
**M1 — Data model & mock sources** → complete  
**M2 — Policy engine** → complete  
**M3 — Permission-aware retrieval pipeline** → complete  
**M4 — TLA+ formal specification** → complete  
**M5 — Audit trail** → complete  
**Next:** M6 — LLM answer agent

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
- [x] **TLA+ formal spec** (`formal/`):
  - `access_control.tla` — query-lifecycle state machine (search → decide → retrieve → answer, with revocation) parameterised by a `BROKEN` flag.
  - `MC_safe` (BROKEN=FALSE) — TLC checks INV1/INV2/INV3/INV4/INV6/INV7, all hold (28 states, no error).
  - `MC_broken` (BROKEN=TRUE, filter-after-retrieval) — TLC finds an INV1 counterexample at depth 4 (over-fetched denied resource reaches the context). This is Demo 5.
  - INV5 (delegation/no-privilege-escalation) deferred to M11 stretch.
  - Verified runnable via bundled `tla2tools.jar` + Java 25; TLC output artifacts gitignored.
- [x] **Audit trail** (`backend/audit/`):
  - `event_schema.py` — canonical `AuditEvent` + deterministic JSON payload (sorted keys, ISO-8601 UTC); `event_from_decision` builds one from a policy `Decision`.
  - `hash_chain.py` — `HashChain`: `event_hash = SHA256(prev_hash + canonical_json)`, append/verify, detects field tampering, broken links, reordering, and deletion; JSON persistence.
  - `audit_query.py` — `AuditQueryEngine` filters by user / resource-substring / query / decision / action / time window and reports chain verification status (Demo 4).
- [x] **93 tests passing**: M1 (33) + M2 (22) + M3 (20) + M5 audit (18).
- [x] Miora added to tech stack.
- [x] Development log started with M0 screenshot.

## What's next

### M6 — LLM answer agent (planned)

**Goal:** orchestrator + answer agent producing grounded, cited answers from
the assembled context, end to end: query → retrieval → answer → audit.

**Outline (module map reserves `backend/agents/`):**

- `orchestrator.py` — `Orchestrator.handle(user, query)` runs the retrieval
  pipeline, appends every decision to the hash chain, calls the answer agent,
  then audits the answer event. Returns `{answer, citations, decisions,
  audit_chain_head}` (matches architecture.md §5 return shape).
- `answer_agent.py` — generates an answer grounded ONLY in the assembled
  context, with citation markers back to allowed resources. Validate every
  citation via `AssembledContext.is_authorized_citation` (INV6). No-metadata-
  leak on empty context: return the canonical "I could not find accessible
  information…" message (feeds Demo 2 / M9).
- **LLM integration:** Tencent Cloud LLM via WorkBuddy/ADP (track requirement).
  Wrap behind an interface with a deterministic stub so tests run offline;
  the real client is swapped in for the demo.
- Tests: answer cites only allowed resources; empty/denied context yields the
  no-leak message; end-to-end run produces a verifiable audit chain.

**Decision to make:** LLM client abstraction (stub vs live) — likely a small
ADR once the WorkBuddy/ADP surface is confirmed.

## Blockers

None. (M6 will need Tencent Cloud LLM credentials for the live path; the
stubbed path unblocks all implementation and tests in the meantime.)

## Key decisions made

- See [decisions/](decisions/) for ADRs.