# Current State — VeriBrain

> **Last updated:** 2026-09-29 (M14 in progress — Hunyuan LLM adapter wired)

## Milestone

**M0 — Project bootstrap** → complete  
**M1 — Data model & mock sources** → complete  
**M2 — Policy engine** → complete  
**M3 — Permission-aware retrieval pipeline** → complete  
**M4 — TLA+ formal specification** → complete  
**M5 — Audit trail** → complete  
**M6 — LLM answer agent** → complete (Hunyuan adapter implemented; stub fallback for offline)  
**M7 — Live revocation handling** → complete  
**M8 — Frontend UI** → complete (REST API + Miora-generated UI wired to it)  
**M9 — No-metadata-leak & negative cases** → complete  
**M10 — End-to-end integration & polish** → complete (demos verified, diagrams polished, project description written)  
**M11 — Hallucination detection layer** → complete (GroundingChecker, INV8, 17 tests)  
**M12 — Data freshness indicators** → complete (updated_at in citations, UI freshness badges, 9 tests)  
**M13 — Prompt-injection detection** → complete (QueryScanner, audit flag, 17 tests)  
**Next:** M14 — full milestone review pass (in progress), then M15 submission prep

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
  - INV5 (delegation/no-privilege-escalation) deferred — action agent removed from roadmap.
  - Verified runnable via bundled `tla2tools.jar` + Java 25; TLC output artifacts gitignored.
- [x] **Audit trail** (`backend/audit/`):
  - `event_schema.py` — canonical `AuditEvent` + deterministic JSON payload (sorted keys, ISO-8601 UTC); `event_from_decision` builds one from a policy `Decision`.
  - `hash_chain.py` — `HashChain`: `event_hash = SHA256(prev_hash + canonical_json)`, append/verify, detects field tampering, broken links, reordering, and deletion; JSON persistence.
  - `audit_query.py` — `AuditQueryEngine` filters by user / resource-substring / query / decision / action / time window and reports chain verification status (Demo 4).
- [x] **Agents** (`backend/agents/`):
  - `llm_client.py` — `LLMClient` protocol + deterministic `StubLLMClient` (ADR-0005). Answer agent depends on the interface, never a provider SDK.
  - `answer_agent.py` — grounded answers from the assembled context; strips citations not backed by context (INV6); returns the canonical no-leak message on empty context (INV7).
  - `grounding_checker.py` — hallucination detection layer (INV8): post-LLM lexical overlap + entity extraction; strips ungrounded sentences from the answer before it reaches the user.
  - `query_scanner.py` — prompt-injection detection: scans queries for instruction-override, role-hijack, prompt-leak, delimiter-injection, and data-exfiltration patterns; flags suspicious queries in the audit trail with `injection_suspected:high|medium`.
  - `orchestrator.py` — `Orchestrator.handle(user, query)` runs injection scan → retrieval → audits every decision → answers → grounding check → audits the answer event; returns `{query_id, answer, citations, decisions, audit_chain_head, no_access}`.
- [x] **Live permission admin** (`backend/policy/admin.py`):
  - `PermissionAdmin` (over the same connectors the pipeline uses) — `revoke_user`/`revoke_role`/`grant_user`/`grant_role` wrap `update_acl` (bumps `acl_version`) and return an `ACLChange` with the version transition (e.g. "v1 → v2") for the policy inspector.
  - Exposed on the orchestrator as `.admin`; a revoke is reflected in the next `handle` call with no reindex (Demo 3), and the audit trail records the DENY at the new ACL version (INV3 end-to-end).
- [x] **REST API layer** (`backend/api/`, FastAPI):
  - `app.py` — factory + module `app` (run `uvicorn backend.api.app:app`); CORS open for local dev; `/health`, `/users` (persona switcher).
  - `state.py` — shared singletons; ONE orchestrator so revocations persist across requests (Demo 3).
  - `query_routes.py` — `POST /query` → answer + citations + decisions (reason/ACL version) + chain head.
  - `audit_routes.py` — `GET /audit` (filter by user/resource/query/decision/action) + `GET /audit/verify`.
  - `admin_routes.py` — `POST /admin/revoke`, `POST /admin/grant` → `ACLChange` with version transition.
  - `schemas.py` — Pydantic wire contract (decoupled from internal dataclasses).
  - Dependencies pinned in `requirements.txt` (FastAPI, uvicorn, pytest, httpx). Server boot smoke-tested.
- [x] **Frontend** (`frontend/`, static — no build step):
  - `index.html` — Miora-generated CRT/phosphor dashboard (persona switcher, query console, policy inspector, audit explorer, revocation controls).
  - `app.js` — wires every panel to the API (`/users`, `/query`, `/audit`, `/audit/verify`, `/admin/revoke|grant`); persona switcher, live ALLOW/DENY inspector, tamper-evidence badge, and auto-re-run after revoke/grant (Demo 3). Graceful offline degradation.
  - Served via any static host (e.g. `python -m http.server` in `frontend/`); backend CORS is open. Verified against live API responses.
- [x] **No-metadata-leak verification (M9)**: end-to-end tests proving a denied
  resource is recorded in the audit trail but never leaks (title/id/content)
  into the answer or citations, and that a denied query and a nonexistent-topic
  query return the *identical* canonical message (denial doesn't confirm
  existence). INV7 was already enforced in the answer agent (M6); M9 added the
  system-level proof — no new source code.
- [x] **185 tests passing**: M1 (33) + M2 (22) + M3 (20) + M5 audit (18) + M6 agents (15) + M7 revocation (10) + M8 API (13) + M9 no-leak (7) + M11 grounding (17) + M12 freshness (9) + M13 injection (17) + Hunyuan adapter (4). (Frontend is static; no automated tests.)
- [x] Miora added to tech stack.
- [x] Development log started with M0 screenshot.
- [x] **M10:** demo runbook (`docs/demo-runbook.md`), getting-started instructions in README, all 5 demos verified end-to-end via API, architecture/trust-boundary diagrams polished, project description written (`docs/project-description.md`), README/architecture.md frontend tech corrected.

## What's next

### M10 — complete

All 5 demo scenarios verified end-to-end via the API:
- Demo 1 (alice): 8 allow / 2 deny, 8 citations across 4 sources.
- Demo 2 (bob): canonical no-leak message, 0 citations, `no_access=true`.
- Demo 3: ACL v1→v2 on revoke, citation drops on re-query.
- Demo 4: 23 audit events for alice, chain verified.
- Demo 5: TLA+ (run via TLC separately).

Architecture & trust-boundary diagrams polished in architecture.md. README and
architecture.md corrected to reflect actual Miora static HTML/JS frontend.
Project description written (`docs/project-description.md`).

### Remaining (manual capture — needs you)

- **Screenshots / recordings:** CodeBuddy/WorkBuddy chat logs (M15 #4, min 3)
  and the working UI running the demos. Several dev-log entries are still marked
  "capture pending".
- **Optional cover image** via Miora (M15 #5, 16:9).
- **Optional demo video** (M15 #6, 5–8 min).

### Then

- **M14** — full milestone review pass: verify every milestone M1–M13 against
  architecture.md, confirm tests pass, confirm invariants hold, fix any drift.
- **M15** — submission prep: confirm all required deliverables, final review.

## Blockers

- **Hunyuan API key needed for live LLM demo.** The adapter is implemented
  (`backend/agents/hunyuan_client.py`) and wired into the orchestrator with
  automatic stub fallback. To go live: `set HUNYUAN_API_KEY=your-key` and
  restart the server. The key is created in the
  [Tencent Cloud Console](https://console.cloud.tencent.com/hunyuan/start).
  The hackathon requirement to use Tencent Cloud AI is satisfied by Hunyuan.

## Key decisions made

- See [decisions/](decisions/) for ADRs.