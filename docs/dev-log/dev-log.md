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

### 2026-09-29 — UI/UX + access-control refinement batch (B1–B5, F1–F6)

- **Tool:** Kiro
- **Task:** Second refinement pass — fixed the lazy LLM output, per-permission access control, document list, inspector merge, pagination, per-citation export, ADP TLS.
- **Summary:**
  - **Root-caused the "Relevant sources found: [1][2][3]" output** — not a prompt I wrote; it's the grounding fallback firing because ADP's live call failed (TLS) → stub → grounding stripped the generic stub text → terminal fallback. Fixed two ways: (B3) ADP client now uses `truststore` so it trusts the OS cert store (works on TLS-inspected networks); (B4) rewrote `StubLLMClient` as an extractive summarizer that pulls real sentences from the context, so its output survives grounding and reads like a real answer.
  - **Verified the roles claim** — the user was right: gating was too coarse (single "privileged" check let compliance_officer revoke/upload). Split into `audit_query` (audit surfaces) vs `manage_permissions` (revoke/grant/upload). Added `audit_query` to security_team. Granular flags on `/users` + `/query`. (B1, B2)
  - **`/export` endpoint** (B5): per-cited-resource `Action.EXPORT` re-check + audit, gated by `export` permission.
  - **Frontend:** document list → cards (F1); policy inspector merged into audit explorer (F2); conditional panel rendering by permission, no locked boxes (F3); audit pagination default 10 + adjustable (F4); per-citation green export button shown only with `export` (F5); permission-denied toasts (F6); trimmed admin-lock to just "ADMIN ACCESS REQUIRED".
  - 212 tests pass. Live-validated the full permission matrix end to end.
  - **Flagged** a pre-existing test-isolation weakness (random-order ACL bleed) as a follow-up, not fixed in this batch.
- **Screenshot captured:** N — capture the polished UI (per-persona admin states, export buttons) for the submission.

---

### 2026-10-09 — Demo-hardening: TOCTOU formal proof, real audit tamper, FinTech narrative

- **Tool:** Kiro
- **Task:** Strengthen the three things that win this hackathon: the formal-methods demo, the tamper-evidence demo, and the pitch narrative. Grounded in verified winner research from the hackathon site.
- **Summary:**
  - **Researched actual winners** (tch.tencentcloud.com): social-good/impact-led projects win; framing rewards "beyond technical complexity". Concluded our rigor is a differentiator *if* sold as FinTech business risk.
  - **TLA+:** extended `Revoke` to fire through the `decided` phase so the model explores the revocation race (TOCTOU). Made safe `Retrieve` re-check the live ACL (proven race-free) and the broken variant trust the stale decide-time snapshot (TLC finds the leak with a concrete trace). Consolidated to one live-flip harness `MC_tianquan.tla`. Verified both runs with TLC. Much stronger than the old filter-after-retrieval variant.
  - **Audit tamper (real):** chain persists to `audit_log.json` on every append; added `/audit/verify-file` that re-reads + re-hashes the file so a genuine hand-edit is caught; UI "verify log file" button replaces the gimmicky in-memory tamper. Found and fixed a real latent bug — `audit_chain or HashChain()` silently discarded a passed-in empty chain (empty `HashChain` is falsy via `__len__`); changed to `is not None`. 5 new file-tamper tests; suite 217 green.
  - **Narrative:** rewrote `docs/project-description.md` to open with the FinTech breach stakes and lead with impact; added `docs/demo-script.md`, a ~4-min rehearsable narration sequencing all demos around the story arc. Fixed stale facts (removed INV5-as-stretch, test count 138→217).
  - Also answered the user's conceptual question: the formal work is load-bearing (proves temporal race safety across all interleavings), not just "tests in disguise" — the permission *check* is simple, the *timing* is what's proven.
- **Screenshot captured:** N — capture the TLC flip + the live log-file tamper for the submission.

---

### 2026-09-29 — Role-based admin gating + UX restructure

- **Tool:** Kiro
- **Task:** Made the admin/audit surfaces genuinely access-controlled (not cosmetic), restructured the dense admin tab, and added a query spinner.
- **Summary:**
  - **Backend (server-enforced):** added `is_privileged()` to `roles.py` (holds `manage_permissions` or `audit_query`) and `backend/api/deps.py` with a `require_privileged` dependency. Gated `/admin/*`, `/audit/*`, and `/upload` to privileged personas via the `X-User-Id` header — 401 without identity, 403 for non-privileged (bob/alice). `/query` now strips DENY details from the response for non-privileged askers (true no-metadata-leak at the wire — the browser never receives denied resource IDs) and returns a `viewer_privileged` flag; aggregate `deny_count` is kept (names no resource). `/users` exposes a `privileged` flag.
  - **Frontend:** admin tab stays visible but shows a server-backed locked state ("ADMIN ACCESS REQUIRED") for non-privileged personas, revealing the full panel only for admin/compliance; the acting `X-User-Id` is sent on all calls. Restructured the dense admin tab — revocation + upload now sit side-by-side as an "operator actions" row. Query console: reduced artificial delay 1200→400ms and added an animated spinner; example-query chips; "querying as [persona]" hint.
  - **Robustness fix (pre-existing bug):** the ADP client was 500ing on this TLS-inspected network (`CERTIFICATE_VERIFY_FAILED` to wss.lke.tencentcloud.com). Added a runtime fallback in the orchestrator: if the live LLM call throws, degrade to the stub (safety unaffected — stub still only sees filtered context). `/query` now returns 200 via fallback instead of crashing.
  - Full suite: 212 tests passing (was 205; +7 gating/query tests). Verified live: alice query 200 with 0 denies shown, bob /audit 403, diana /audit 200.
- **Screenshot captured:** N — capture the polished UI + the locked admin state for the submission.

---

### 2026-09-29 — UI/UX polish pass (demo prep)

- **Tool:** Kiro
- **Task:** Resumed the frontend polish pass started in a prior session (dim text + dropdown issues) and did a broader UX review.
- **Summary:** Primary fix — the dim text was near-unreadable (`#6b6150`/`#4a4540` on a dark bg, below WCAG AA). Brightened the full dim palette across `index.html` and `app.js`: muted text now `#9a8e78`+, section labels `#c2b79f`, body `#f0e6d2`; also fixed a double-dim answer-processing state (dim color at 0.6 opacity). Dropdown — the persona dropdown was already fully implemented (not a stub); hardened it with `pointer-events:none` on the trigger's child icons so FontAwesome's JS `<svg>` swap can't swallow the click. UX additions: clickable example-query chips tied to the demo scenarios (fixes the blank-input "don't know what to ask" problem), a "querying as [persona]" hint in the query console, and an ASK-button busy/disabled state to prevent double-submits. Verified both servers run and the query path is intact (alice: 7 allow / 2 deny, 4 citations). Committed as one `fix(ui)`.
- **Screenshot captured:** N — capture the polished UI for the submission.

---

### 2026-10-10 — Auditability realignment (answer capture, time-window query, export-in-preview)

- **Tool:** Kiro
- **Task:** Closed three auditability/UX gaps surfaced while pressure-testing the "inspectable AI" story: (1) answer text wasn't in the audit trail, (2) the audit trail wasn't time-queryable, (3) a view-only persona could preview content but the export button lived on the citation card.
- **Summary:** Gap 1 — added a hashed `detail` field to `AuditEvent` (added to `_PAYLOAD_FIELDS`, so tamper-evident) threaded through `event_schema`, `hash_chain.append_decision`, the orchestrator's answer-event append (`detail=answer.text`), and the `AuditEventModel` wire schema; UI audit table now shows the AI's answer text (italic/quoted, 90-char truncation + full tooltip) in the detail column. `detail` defaults to `""` so existing chains/hash tests are unaffected (verified chain stays valid post-query). Gap 2 — `/audit` now accepts `since`/`until` (ISO or plain date, naive→UTC, `until` bumped to end-of-day client-side); UI gained a second filter row with date inputs + "last 7 days" + "clear"; inspectors can now answer "what did alice access last week?" Gap 3 — removed the per-citation export button (cards are click-to-preview only); the green `export ↓` button now lives inside the source-preview window and renders ONLY when the persona holds `export`. Live-verified: answer text captured in `detail`; `since=2099`→0 / `since=2000`→all / `user_id` scoping; `can_export` flags match (alice/bob none; charlie/diana/jdoe/erin/frank yes). 217 tests pass; no new diagnostics.
- **Screenshot captured:** N — capture the audit explorer (detail column + time filters) and the preview export button for the submission.

---

### 2026-10-10 — NL audit search + preview/tab permission-gating + answer-text expand

- **Tool:** Kiro
- **Task:** Follow-ups from the auditability pass: (B) let a compliance officer type a plain-English question into the audit explorer; gate the whole source-preview panel on download permission; hide the Admin tab entirely for non-privileged personas; add an expand/collapse to the full answer text in the inspector; rename the export button to "download"; and answer the "LLM with deterministic fallback" question for both the audit search and the main query box.
- **Summary:** Built `backend/audit/nl_query.py` — a deterministic NL→AuditQuery parser (user by id/display-name, time windows today/yesterday/last N days|weeks|months/last week|month, allow/deny keywords, quoted resource substring), conservative (unparseable → unset filter, not a guess). New `GET /audit/search?q=` endpoint (gated by `audit_query`, 403 for bob verified) returns the structured result plus the parse `interpretation`/`parts` for transparency. UI gained an "ask the audit trail" box above the filters. Deliberately **no LLM dependency** — deterministic is the right default for an audit tool (offline, reproducible); an LLM can be layered on later with this as the fallback. Clarified that the main query box ALREADY implements "LLM with deterministic fallback": the orchestrator tries the live ADP LLM and degrades to the StubLLMClient extractive summarizer on any failure, with safety unaffected (both only see filtered context). Frontend: gated the entire source-preview panel on `export` (view raw content ⇒ can copy out ⇒ treat as export; without it, citation cards are non-interactive metadata); hid the Admin tab button entirely for personas lacking audit+manage (with fallback to the query tab if they were on it); replaced the 90-char answer-text truncation with a per-row expand/collapse toggle; renamed "export ↓" → "download ↓". Live-verified NL search (alice last week = 12 allow / 6 deny; name-resolution John→jdoe; gibberish → full-log warning). 232 tests pass (+15 NL-parser tests); no new diagnostics.
- **Screenshot captured:** N — capture the NL audit search (question + interpretation) and the gated preview for the submission.

---

### 2026-10-10 — Grounding-fallback root-cause fix + gating/UX polish

- **Tool:** Kiro
- **Task:** Fix the recurring "Relevant sources found: [1]" / empty-answer output (user flagged it as an apparent invariant regression); hide tabs completely for non-privileged personas without reflowing the layout; make the source-preview panel re-gate immediately on persona switch; and decide whether the audit NL search should answer in prose or keep the table.
- **Summary:** **Root-caused the bad output** — it was neither a lazy LLM nor a broken invariant. The orchestrator's grounding-checker (INV8) fallback emitted `"Relevant sources found: {markers}"` (or `""`) whenever every answer sentence got stripped. But the grounding checker is a hallucination guard for *generative* output, while the answer text is already citation-validated (INV6) and the deterministic stub's text is extracted verbatim from authorized context — so a total-strip was nearly always an over-strip (markdown headers breaking sentence splitting), not a hallucination. Fixed by keeping the citation-validated pre-grounding text on total-strip instead of the placeholder; safety unchanged (only authorized/cited content can appear). Verified live: placeholder/empty answers gone; genuine no-access still returns the canonical message or an honest "could not find". **Frontend:** tab bar now `visibility:hidden` (not display:none) for personas lacking admin access so other tabs aren't hinted at and the vertical space is preserved (no reflow); source-preview panel now hides immediately and re-gates citations on persona switch via a remembered `state.lastAnswer` (was only checked at click time); audit NL search gained a deterministic one-line summary ("Found N events (A allowed, D denied)") above the hash-chained table — kept the verifiable event table as the primary artifact (it's the trust anchor) with the NL summary as the approachable entry point, no LLM. 232 tests pass; no new diagnostics.
- **Screenshot captured:** N — capture the fixed answers, hidden tab bar, and NL audit summary for the submission.

---

### 2026-10-10 — Preview-panel presence model + clear-query-on-switch

- **Tool:** Kiro
- **Task:** Make the source-preview panel presence-gated (visible-but-empty for export-capable personas, gone for others) rather than only appearing on click; clear the query session when switching accounts. Also clarified for the user that INV8 stripping is NOT gone — only the total-strip placeholder case changed.
- **Summary:** Reworked the preview into an explicit empty/populated state machine in `frontend/`. The panel (`#resource-preview`) is now shown in an empty "click a cited source above…" ready state whenever `state.canExport`, and hidden entirely otherwise — driven by a new `syncPreviewPanel()` called on every persona switch (was: panel hidden until a citation click). Clicking a citation swaps empty→populated (content + download + close); the close button now resets to the empty state instead of hiding the whole panel; a new query resets to empty too. Added `clearQuery()` (clears input, answer, citations, resets preview) called from `selectPersona` so switching accounts starts a clean session — results belong to the persona that ran them. Added `#preview-empty` placeholder and split the id/title/content into toggle-able populated elements in `index.html`. Confirmed the INV8 grounding checker still strips ungrounded sentences in the normal partial case; only pass-3's total-strip edge case changed. 232 tests pass; no new diagnostics; all frontend-only (served live, no restart).
- **Screenshot captured:** N — capture the empty-ready preview panel and a populated one for the submission.

---

### 2026-10-10 — Removed upload UI, added permissions inspector

- **Tool:** Kiro
- **Task:** Decide the fate of the document-upload panel (user flagged it as debug-ish and off-thesis) and repurpose the space. Agreed: remove the upload UI (keep the backend connector, which proves extensibility), and add a read-only permissions inspector in its place — a live "who can access what" view that strengthens the core access-control story.
- **Summary:** Removed the document-ingestion panel from the admin tab and its `uploadDocument`/`listUploads` JS; kept the backend `UploadConnector` + `/upload` routes unsurfaced (extensibility is an architecture/pitch point, not a UI feature). Built `backend/policy/inspector.py` — a `PermissionsInspector` with three read-only lookups computed via the real PolicyEngine (not raw ACL membership): by user (every resource with can_read/can_export + how access is granted: user-grant vs role:<name> vs denied, plus the user's roles), by role (member users + granted resources), by resource (raw ACL + effective readers). Exposed as `/admin/permissions/{user,role,resource}/…` + a `/admin/permissions/resources` picker list, all gated by `manage_permissions` (bob → 403 verified). Frontend: a lookup-kind dropdown + searchable combo + rich result rendering in the old upload slot; resource options fetched lazily when a manage-capable persona opens the admin tab. Live-verified the demo loop: revoke `engineer` from db-migration-plan → alice leaves effective_readers (frank/jdoe remain) → grant restores. 12 inspector unit tests; 244 total pass; no new diagnostics.
- **Screenshot captured:** N — capture the permissions inspector (user/role/resource lookups) and the revoke→inspector live update for the submission.

---

### 2026-10-11 — Independent review against the handbook + fixes

- **Tool:** AI coding assistant (CodeBuddy credits exhausted)
- **Task:** Independent end-to-end review of the project against the Aspire challenge and the handbook's submission requirements, then fix everything it found.
- **Summary:** The review found the demo question collapsed to one Slack thread (naming a platform filtered out the other three) — now a ranking boost, restoring 8 allow / 2 deny across 4 sources (ADR-0006). Found the shared ADP client reused one conversation, giving the model memory of other users' context — every call is now a fresh conversation (ADR-0007); also fixed UTF-8 decoding of the ADP stream. Secured the source-preview endpoint (header identity, `export` required, every view audited, denied ≡ not found). Fixed the grounding checker over-stripping correct live answers and surfaced the removed-sentence count. Recorded the question on every audit event; plain-English audit search now resolves resource/space/project phrases and reports what it didn't understand. UI: clickable [n] citations, query-grouped audit table, accessibility pass with clean mode, vendored Tailwind (no CDNs). New architecture diagram; stale docs refreshed. 273 tests.
- **Screenshot captured:** N

---

### 2026-10-11 — Audit citation map, tool credits, demo script, polish

- **Tool:** AI coding assistant (CodeBuddy credits exhausted)
- **Task:** Make the logged answer's [1]/[2] traceable in the audit explorer; credit ADP and Miora; rewrite the demo script against the five required scenarios; final polish.
- **Summary:** The answer audit event now stores a hashed marker → resource citation map; the audit explorer shows a `cited:` key under each answer and marks every allowed document "citation [n]" or "not cited". Project description and README credit each Tencent tool (CodeBuddy for planning and the core build, ADP for every LLM answer, Miora for the UI design and cover image). Demo script rewritten (~5½ min + reflection) to name the track, cover all five scenarios, and show the architecture; the diagram gained a "verifies" link from the TLA+ model to the pipeline. Cover image finalised (Miora, 16:9). Removed hard-coded user paths. 275 tests.
- **Screenshot captured:** N

---

### YYYY-MM-DD — Mn: milestone/task

- **Tool:** CodeBuddy / WorkBuddy / Miora
- **Task:** What was being worked on
- **Summary:** What the conversation accomplished
- **Screenshot captured:** Y/N

-->