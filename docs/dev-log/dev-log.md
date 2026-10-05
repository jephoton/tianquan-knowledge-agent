# Development Log — Tianquan 天权

> **Purpose:** Track CodeBuddy / WorkBuddy / Miora usage throughout development. This is a **required submission deliverable** — the handbook requires a minimum of 3 screenshots or screen recordings of chat logs from CodeBuddy or WorkBuddy during the development process.
>
> **Rule:** Take a screenshot at the end of any significant CodeBuddy/WorkBuddy session. Don't wait until M13 — conversation history cannot be reconstructed retroactively.

## Entries

### 2026-09-27 — M0: Project bootstrap

- **Tool:** CodeBuddy
- **Task:** Read Track 4 (Aspire FinTech) challenge from handbook PDF. Analyzed the challenge requirements. Designed the Tianquan project concept. Wrote formal plan, architecture, and ADRs. Scaffolded repo structure.
- **Summary:** Initial project planning session. Read the Aspire "Internal Brain" challenge. Compared user's original idea (formally constrained enterprise agents) against the track requirements. Refined scope to focus on permission-aware retrieval as the core, with formal methods as the differentiator. Created the handoff layer (`docs/`), roadmap with 13 milestones, 3 ADRs, and repo skeleton.
- **Screenshot captured:** Y — [Screenshot 2026-09-27 215926.png](Screenshot%202026-09-27%20215926.png)

---

### 2026-09-28 — M2: Policy engine + handoff-layer steering

- **Tool:** CodeBuddy
- **Task:** Onboarded to the repo via the handoff layer. Added a global-style steering rule for the persistent handoff layer + conventional-commit discipline. Committed and completed M2 (policy engine).
- **Summary:** Read the full handoff layer (plan, architecture, current-state, ADRs, dev-log) to understand Tianquan. Created `.kiro/steering/handoff-layer.md` codifying the docs/ handoff structure and commit conventions. Found uncommitted M2 policy code (policy_engine, permission_mapping, freshness_checker) with no tests; verified it imports and matches the data model, wrote 22 positive/negative/freshness tests (all 55 tests pass), then committed engine and tests as separate atomic commits. Updated current-state.md and plan.md to mark M2 complete and set M3 (retrieval pipeline) as next.
- **Screenshot captured:** Y — [Screenshot 2026-09-28 100832.png](Screenshot%202026-09-28%20100832.png), [Screenshot 2026-09-28 100923.png](Screenshot%202026-09-28%20100923.png)

---

### 2026-09-28 — M3 planning: retrieval pipeline

- **Tool:** CodeBuddy
- **Task:** Committed the hackathon handbook as reference. Planned M3 (permission-aware retrieval pipeline).
- **Summary:** Reviewed connector interfaces to ground the plan. Wrote ADR-0004 choosing keyword/token-overlap candidate search over vector embeddings for V1 (small corpus, determinism, no external deps, filter is the real gate). Broke M3 into indexer → candidate_search → permission_filter → context_assembler + integration tests, with the filter re-fetching live ACLs so over-fetched candidates cannot leak revoked content. Recorded the task breakdown and integration-test plan (INV1/INV2, over-fetch safety, revocation, role differentiation) in current-state.md.
- **Screenshot captured:** N — capture at end of session.

---

### 2026-09-28 — M3: retrieval pipeline implementation

- **Tool:** CodeBuddy
- **Task:** Implemented the M3 permission-aware retrieval pipeline end to end.
- **Summary:** Built `indexer` (connector snapshot with ACL-version stamp), `candidate_search` (deterministic keyword/token-overlap, over-fetch), `permission_filter` (re-fetches live ACLs, runs the policy engine, records freshness, drops denied resources), `context_assembler` (bounded, citation-marked context with INV6 hook), and `pipeline` wiring the four. Verified the safety property manually: contractor Bob gets zero security-breach content while security-team Charlie sees the confidential report. Wrote 20 integration tests (INV1/INV2/INV3, over-fetch safety, revocation-after-indexing honored without reindex, contractor⊂engineer). Full suite: 75 passing. Marked M3 complete and outlined M4 (TLA+) in the handoff layer.
- **Screenshot captured:** N — capture at end of session.

---

### 2026-09-28 — M4: TLA+ formal specification

- **Tool:** CodeBuddy + TLA+ VS Code extension (TLC via bundled tla2tools.jar, Java 25)
- **Task:** Wrote and model-checked the TLA+ access-control specification.
- **Summary:** Modeled the query lifecycle (search → decide → retrieve → answer, with revocation) as a state machine in `access_control.tla`, parameterised by a `BROKEN` flag. Encoded INV1–INV4, INV6, INV7 (INV5 delegation deferred to M11). Built MC harness modules to supply the `Authorized` ACL function that a .cfg literal can't express. Ran TLC: `MC_safe` passes all invariants (28 states); `MC_broken` (filter-after-retrieval) produces an INV1 counterexample at depth 4 — an over-fetched, denied resource (r2) reaches alice's context. That's the Demo 5 payoff. Cleaned up TLC output artifacts and gitignored them. Marked M4 complete, outlined M5 (audit trail).
- **Screenshot captured:** N — capture at end of session (TLC output worth capturing for the demo).

---

### 2026-09-28 — M5: tamper-evident audit trail

- **Tool:** CodeBuddy
- **Task:** Implemented the M5 hash-chained audit trail and query API.
- **Summary:** Built `event_schema` (canonical AuditEvent with deterministic sorted-key JSON payload, `event_from_decision`), `hash_chain` (`event_hash = SHA256(prev_hash + canonical_json)`, append/verify, JSON persistence), and `audit_query` (filter by user/resource-substring/query/decision/action/time window, reports chain verification — backs Demo 4). Verified end to end against the M3 pipeline: 6 real decisions chained and verified, tampering a field detected. Wrote 18 tests covering clean verification, field tampering, decision-flip, broken links, reordering, deletion, INV4 (every pipeline decision audited incl. denies), query filters, and time windows. Full suite: 93 passing. Marked M5 complete, outlined M6 (LLM answer agent) and flagged the LLM-client stub-vs-live decision.
- **Screenshot captured:** N — capture at end of session.

---

### 2026-09-28 — M6 pre-work: LLM client decision (ADR-0005)

- **Tool:** CodeBuddy
- **Task:** Decided the LLM integration approach before building M6, to avoid technical debt.
- **Summary:** Discovered the WorkBuddy API is paywalled (requires Pro, not currently available). Decided to abstract the LLM behind an `LLMClient` interface: `StubLLMClient` (deterministic, offline) as the dev/test default, `TencentLLMClient` (WorkBuddy/ADP) as the demo adapter selected via config. Rationale: permission safety (INV1/INV2) is pre-LLM, so the model is a leaf/swappable component — "which LLM" is a deployment choice, not architecture. Recorded as ADR-0005 and logged the WorkBuddy Pro paywall as a tracked blocker with fallbacks (CodeBuddy usage proof; optional local model for the demo). No code written yet.
- **Screenshot captured:** N — capture at end of session.

---

### 2026-09-28 — M6: answer agent + orchestrator (LLM-client decision)

- **Tool:** CodeBuddy
- **Task:** Settled the LLM-provider question (ADR-0005) and implemented M6.
- **Summary:** Discussed WorkBuddy vs open-source LLM. Key realization: safety (INV1/INV2) lives in retrieval, so the LLM is swappable behind an interface — that abstraction is the debt-avoiding decision, and the concrete provider can be deferred. Wrote ADR-0005 (interface Accepted; provider Open). Discovered WorkBuddy API needs a Pro upgrade that isn't available, so recorded CodeBuddy (already the usage-proof tool) and a local open-source model as fallbacks — submission is not at risk. Built `llm_client` (LLMClient protocol + deterministic StubLLMClient), `answer_agent` (grounds on context, strips unauthorized citations = INV6, canonical no-leak message on empty context = INV7), and `orchestrator` (query → retrieval → audit decisions → answer → audit answer event, returns the architecture §5 shape). Verified end to end: Alice gets a cited answer, Bob gets the no-leak message, combined audit chain verifies. 15 tests; full suite 108 passing. Marked M6 complete, outlined M7 (live revocation — mostly exposing existing enforcement).
- **Screenshot captured:** N — capture at end of session.

---

### 2026-09-28 — M7: live revocation handling (Demo 3)

- **Tool:** CodeBuddy
- **Task:** Implemented live permission revocation/grant and wired it into the orchestrator.
- **Summary:** Built `PermissionAdmin` (`backend/policy/admin.py`) with `revoke_user`/`revoke_role`/`grant_user`/`grant_role`, each wrapping the connectors' `update_acl` (which bumps `acl_version`) and returning an `ACLChange` capturing the version transition for the policy inspector. User revocation uses deny-list precedence so it's definitive. Exposed it on the orchestrator as `.admin` over the same connector instances the pipeline uses, so a revoke propagates to the next query with no reindex — this is the whole point of the M3 live-ACL design paying off. Verified Demo 3 end to end: Alice cites db-migration-plan, revoke_role('engineer') bumps v1→v2, next query excludes it, audit records the DENY at v2. 10 tests; full suite 118 passing. Marked M7 complete, outlined M8 (frontend UI) and flagged that M8 likely needs a thin FastAPI layer first.
- **Screenshot captured:** N — capture at end of session.

---

### 2026-09-28 — M8 (part 1): REST API layer

- **Tool:** CodeBuddy
- **Task:** Built the FastAPI layer the frontend will code against (frontend itself deferred).
- **Summary:** Added `backend/api/` — an app factory (`app.py`), shared state with a single orchestrator so revocations persist across requests (`state.py`), Pydantic wire models (`schemas.py`), and three routers: `/query`, `/audit` + `/audit/verify`, `/admin/revoke` + `/admin/grant`, plus `/health` and `/users` for the persona switcher. The API is a thin adapter — all authorization/retrieval/audit logic stays in the layers below. Introduced the project's first runtime deps (FastAPI, uvicorn) and created a pinned `requirements.txt`. Smoke-tested that uvicorn boots and `/health` responds. Wrote 13 API tests via FastAPI TestClient, including Demo 3 (revoke → next query excludes the resource) over HTTP; full suite 131 passing. Updated architecture.md to mark the API implemented. Frontend (Miora React UI) remains for a later session.
- **Screenshot captured:** N — capture at end of session.

---

### 2026-09-28 — M8 (part 2): port + wire Miora UI

- **Tool:** CodeBuddy + Miora
- **Task:** Ported the Miora-generated dashboard into the repo and wired it to the API.
- **Summary:** Miora produced a single static HTML file (CRT/phosphor-terminal styling) with all the right panels but hardcoded mock data and fake personas. Moved it to `frontend/index.html`, added stable IDs/hooks to each panel, replaced mock personas with the real seed users, and wrote `frontend/app.js` to wire everything to the live API: persona switcher (`/users`), query console (`/query`), policy inspector rendering real decisions with reasons + ACL versions, audit explorer with filters + tamper-evidence badge (`/audit`, `/audit/verify`), and revocation controls (`/admin/revoke|grant`) that auto-re-run the last query so Demo 3 is visible live. Kept Miora's visual design intact. Verified all API response shapes against a running server (users, query, audit) then shut it down. Static frontend, no build step; graceful offline degradation. Updated frontend README. M8 complete (API + UI). Next: M9 (no-metadata-leak — largely already satisfied).
- **Screenshot captured:** N — capture the wired UI for the submission (Miora + working demo).

---

### 2026-09-28 — M9: no-metadata-leak verification (Demo 2)

- **Tool:** CodeBuddy
- **Task:** Proved the negative-case / no-metadata-leak property end to end.
- **Summary:** No new source code — INV7 was already enforced in the answer agent (M6) and denied decisions were already audited (M5). Added 7 end-to-end tests through the orchestrator asserting the full Demo 2 property: a denied resource (the confidential Q3 breach report) appears in the audit trail as a DENY but its title/id/distinctive content never leak into the answer or citations, the deny reason is recorded for auditors but not shown to the user, and — the sharpest one — a denied query returns the SAME canonical message as a genuinely nonexistent topic, so the user cannot tell "denied" from "does not exist." Control test confirms security_team still sees the content. Full suite 138 passing. Marked M9 complete; next is M10 (integration & polish: demo runbook, run instructions, screenshots).
- **Screenshot captured:** N — capture at end of session.

---

### 2026-09-28 — M10 (part 1): demo runbook + run instructions

- **Tool:** CodeBuddy
- **Task:** Packaging for the demo — runbook and getting-started docs.
- **Summary:** Wrote `docs/demo-runbook.md`, a step-by-step script for all 5 demo scenarios (personas, exact queries, expected outcomes, talking points). Verified every query against the running API first so the numbers are accurate: Demo 1 (alice) = 8 allow / 2 deny with the two security docs filtered; Demo 2 (bob) = canonical no-leak message; Demo 3 = ACL v1→v2 and the citation drops on auto-re-run; Demo 5 TLC commands. Added a "restart backend to reset state" note (in-memory audit chain + ACL changes persist). Replaced the top-level README's TBD setup section with real getting-started + run instructions and linked the runbook. Remaining M10 items are manual capture (screenshots/recordings, optional Miora cover) that need the user.
- **Screenshot captured:** N — this is the session to capture (UI + CodeBuddy) for M13 #4.

---

### 2026-09-29 — M10: end-to-end integration verification & polish

- **Tool:** CodeBuddy
- **Task:** Regenerated context from the handoff layer (M0–M9 all complete). Verified all 5 demo scenarios end-to-end via the API. Polished architecture/trust-boundary diagrams for submission. Wrote project description document (M13 #3). Corrected README and architecture.md frontend tech stack to reflect actual Miora-generated static UI (not React+TS).
- **Summary:** Re-read all docs/ files to rebuild context after significant progress. Started the backend API and exercised all 4 API-based demos programmatically: Demo 1 (alice: 8 allow / 2 deny, 8 citations across 4 sources), Demo 2 (bob: canonical no-leak message, 0 citations), Demo 3 (revoke engineer role from db-migration-plan, ACL v1→v2, citation drops on re-query), Demo 4 (23 audit events for alice, chain verified). All assertions passed. Updated README and architecture.md to accurately reflect the Miora static HTML/JS frontend (was still listed as React+TypeScript). Created `docs/project-description.md` covering overview, real-world scenario, solution design, formal verification, business value, and demo scenarios — fulfills M13 #3. Remaining M10 items are manual capture (screenshots/recordings of CodeBuddy chat logs + working UI) that need the user.
- **Screenshot captured:** N — this session (capture for M13 #4)

---

### 2026-09-29 — M11/M12/M13: hallucination detection, freshness indicators, prompt-injection detection

- **Tool:** CodeBuddy
- **Task:** Implemented three new value-add milestones (replaced the old M11 action agent and M12 Dafny stretch goals).
- **Summary:**
  - **M11 (Hallucination detection layer):** Created `grounding_checker.py` — runs post-LLM, pre-return. Two deterministic checks: (1) lexical token overlap between answer sentences and context, (2) entity extraction verifying all named entities/numbers appear in the context. Ungrounded sentences are stripped (INV8: GroundedAnswerOnly). Wired into the orchestrator with a citation-only fallback when everything is stripped. 17 tests covering positive cases, negative cases, structurally-similar hallucination, numbers, short sentences, empty context, and orchestrator integration.
  - **M12 (Data freshness indicators):** Added `updated_at` field to `Citation` dataclass, populated from `Resource.updated_at` in the context assembler. Threaded through to `CitationModel` in the API schema and the query route. Frontend `app.js` shows color-coded freshness badge per citation (green <24h, amber <7d, red >7d). 9 tests.
  - **M13 (Prompt-injection detection):** Created `query_scanner.py` — scans queries for 5 injection pattern categories (instruction override, role hijack, prompt leak, delimiter injection, data exfiltration). Suspicious queries flagged in the audit trail reason field with `injection_suspected:high|medium`. Does NOT block queries — defense-in-depth, not a gate. Wired into the orchestrator. 17 tests.
  - **Roadmap revised:** Old M11 (action agent) and M12 (Dafny) removed — action agent misaligns with problem statement and adds attack surface; Dafny redundant with TLA+ for hackathon. New milestones M11–M13 added, M14 (full review pass) and M15 (submission prep) shifted. INV8 added to invariant table.
  - Full suite: 181 tests passing, zero regressions.
- **Screenshot captured:** N — capture at end of session.

---

### 2026-09-29 — UI/UX polish pass (demo prep)

- **Tool:** Kiro
- **Task:** Resumed the frontend polish pass started in a prior session (dim text + dropdown issues) and did a broader UX review.
- **Summary:** Primary fix — the dim text was near-unreadable (`#6b6150`/`#4a4540` on a dark bg, below WCAG AA). Brightened the full dim palette across `index.html` and `app.js`: muted text now `#9a8e78`+, section labels `#c2b79f`, body `#f0e6d2`; also fixed a double-dim answer-processing state (dim color at 0.6 opacity). Dropdown — the persona dropdown was already fully implemented (not a stub); hardened it with `pointer-events:none` on the trigger's child icons so FontAwesome's JS `<svg>` swap can't swallow the click. UX additions: clickable example-query chips tied to the demo scenarios (fixes the blank-input "don't know what to ask" problem), a "querying as [persona]" hint in the query console, and an ASK-button busy/disabled state to prevent double-submits. Verified both servers run and the query path is intact (alice: 7 allow / 2 deny, 4 citations). Committed as one `fix(ui)`.
- **Screenshot captured:** N — capture the polished UI for the submission.

---

### YYYY-MM-DD — Mn: milestone/task

- **Tool:** CodeBuddy / WorkBuddy / Miora
- **Task:** What was being worked on
- **Summary:** What the conversation accomplished
- **Screenshot captured:** Y/N

-->