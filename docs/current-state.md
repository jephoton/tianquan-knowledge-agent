# Current State — VeriBrain

> **Last updated:** 2026-09-28 (M7 complete)

## Milestone

**M0 — Project bootstrap** → complete  
**M1 — Data model & mock sources** → complete  
**M2 — Policy engine** → complete  
**M3 — Permission-aware retrieval pipeline** → complete  
**M4 — TLA+ formal specification** → complete  
**M5 — Audit trail** → complete  
**M6 — LLM answer agent** → complete (stubbed LLM; live provider deferred, see ADR-0005)  
**M7 — Live revocation handling** → complete  
**Next:** M8 — Frontend UI

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
- [x] **Agents** (`backend/agents/`):
  - `llm_client.py` — `LLMClient` protocol + deterministic `StubLLMClient` (ADR-0005). Answer agent depends on the interface, never a provider SDK.
  - `answer_agent.py` — grounded answers from the assembled context; strips citations not backed by context (INV6); returns the canonical no-leak message on empty context (INV7).
  - `orchestrator.py` — `Orchestrator.handle(user, query)` runs retrieval → audits every decision → answers → audits the answer event; returns `{query_id, answer, citations, decisions, audit_chain_head, no_access}`.
- [x] **Live permission admin** (`backend/policy/admin.py`):
  - `PermissionAdmin` (over the same connectors the pipeline uses) — `revoke_user`/`revoke_role`/`grant_user`/`grant_role` wrap `update_acl` (bumps `acl_version`) and return an `ACLChange` with the version transition (e.g. "v1 → v2") for the policy inspector.
  - Exposed on the orchestrator as `.admin`; a revoke is reflected in the next `handle` call with no reindex (Demo 3), and the audit trail records the DENY at the new ACL version (INV3 end-to-end).
- [x] **118 tests passing**: M1 (33) + M2 (22) + M3 (20) + M5 audit (18) + M6 agents (15) + M7 revocation (10).
- [x] Miora added to tech stack.
- [x] Development log started with M0 screenshot.

## What's next

### M8 — Frontend UI (planned)

**Goal:** Miora-generated React UI surfacing all demo scenarios — query console,
policy inspector (ALLOW/DENY cards with reason + permission source + ACL
version), audit explorer, and a demo persona switcher.

**Note:** the backend already returns everything the UI needs. `QueryResponse`
carries `answer`, `citations`, `decisions` (each with reason + acl_version +
policy_version), and `audit_chain_head`; `AuditQueryEngine` backs the audit
explorer; `ACLChange.version_transition` backs the revocation demo panel.

**Outline:**

- Likely needs a thin FastAPI layer (`backend/api/`) to expose the orchestrator,
  audit query, and admin actions over REST — the module map already reserves
  `query_routes.py`, `audit_routes.py`, `admin_routes.py`.
- Miora generates the React components against those endpoints.
- Persona switcher = pick a seed user (alice/bob/charlie/diana/…) and re-run.
- Wire the 4 UI-visible demo scenarios (1–4); Demo 5 (TLA+) is shown separately.

**Decision to consider:** whether to build the FastAPI layer as its own small
milestone before the UI, since M8 depends on it. Fold-in vs split — decide at
M8 start.

## Blockers

- **WorkBuddy API requires a Pro upgrade** (not currently available), so the
  live Tencent LLM path cannot be exercised yet. Mitigated by ADR-0005: M6 is
  built and tested against `StubLLMClient` offline; the WorkBuddy adapter is a
  config-level swap once Pro access lands. Fallbacks if it never does:
  CodeBuddy (already the documented dev tool / usage proof) and/or a local
  open-source model for the live demo. **This blocks the live-LLM demo path
  only — not M7 or any further implementation.**

## Key decisions made

- See [decisions/](decisions/) for ADRs.