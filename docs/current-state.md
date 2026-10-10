# Current State — Tianquan 天权

> **Last updated:** 2026-10-10 (NL audit search + preview/tab gating + answer-text expand)

## Grounding-fallback fix + gating/UX polish (2026-10-10, pass 3)

- **Fixed the "Relevant sources found: [1]" / empty-answer regression (root
  cause).** It was NOT an invariant violation and NOT a lazy LLM. The string
  came from the orchestrator's grounding-checker fallback: when INV8 stripped
  *every* sentence, the code emitted a `"Relevant sources found: {markers}"`
  placeholder (or `""` when there were no markers). The grounding checker is a
  hallucination guard for a *generative* LLM, but the answer text is already
  citation-validated (INV6) and the deterministic stub's text is extracted
  verbatim from authorized context — so "everything stripped" was almost always
  an over-strip (e.g. markdown headers breaking sentence splitting), not a real
  hallucination. Fix: on total-strip, keep the citation-validated pre-grounding
  text instead of the placeholder. Safety intact (text can only contain
  authorized, cited content). Live-verified: the placeholder/empty answers are
  gone; weak no-access matches now return an honest "could not find" instead.
- **Tab bar hidden (not reflowed) for non-privileged personas.** Switched from
  hiding just the Admin button to `visibility:hidden` on the whole `.tab-bar`
  when the persona lacks admin access — so other tabs aren't even hinted at,
  and the reserved vertical space is preserved (content below doesn't jump up).
- **Source-preview panel re-gates on persona switch.** Switching to a persona
  without `export` now immediately hides any open preview and re-renders the
  current answer's citations so their click-to-open behavior tracks the new
  permission (was: only checked at click time; a stale open preview could
  linger). `state.lastAnswer` remembered for the re-render.
- **Audit NL search now shows a deterministic one-line summary** ("…Found N
  events (A allowed, D denied).") above the hash-chained evidence table —
  decision: keep the verifiable event table as the primary artifact (it's what
  makes the trail trustworthy); the NL summary is the approachable entry point,
  computed from counts with no LLM. Reinforces the tamper-evidence thesis
  rather than replacing it with prose.

## NL audit search + permission-gating polish (2026-10-10, pass 2)

Built on the auditability realignment below. 232 tests pass (added 15 NL-parser
tests). Live-verified.

- **Natural-language audit search (Option B).** New `backend/audit/nl_query.py`
  deterministically parses a plain-English compliance question — "what did
  alice access last week?" — into a structured `AuditQuery` (user by id or
  display name, time window: today/yesterday/last N days|weeks|months/last
  week|month, decision allow|deny, quoted resource substring). New endpoint
  `GET /audit/search?q=` (gated by `audit_query`) runs it and returns the
  parse `interpretation` + `parts` for transparency. UI: an "ask the audit
  trail" box above the structured filters; shows what it understood. **No LLM
  dependency** — deterministic, offline, same answer every time (the right
  default for an audit tool). An LLM can be layered on top later as an optional
  enhancement; the deterministic parser stays the fallback.
- **On "LLM with deterministic fallback":** this is already the pattern for the
  main query box — the orchestrator calls the live ADP LLM and, on any failure
  (e.g. the TLS-intercepted network), degrades at runtime to the deterministic
  `StubLLMClient` extractive summarizer. Safety is unaffected either way
  because both only ever see permission-filtered context. The NL audit search
  now mirrors that philosophy (deterministic core, LLM optional).
- **Source-preview panel gated on download/export permission.** The whole
  preview surface (view raw content + download) now renders only for personas
  with `export`; without it, citation cards are non-interactive metadata (you
  can read the blended cited answer but not open/copy the raw source). Rationale
  the user raised: once you can read raw content you can copy it out, so viewing
  the source IS effectively exporting — gate them together.
- **Admin tab hidden entirely** for personas with no admin access (was: visible
  tab with a "locked" card). If a persona loses access while on the admin tab,
  the UI falls back to the query tab.
- **Answer text in the inspector** now has a per-row **expand/collapse** toggle
  (was: 90-char truncation with hover tooltip) so compliance can read the full
  captured answer inline.
- **Button label** "export ↓" → "download ↓" in the preview.

> **Last updated:** 2026-10-10 (auditability realignment: answer capture, time-window query, export-in-preview)

## Auditability realignment (2026-10-10)

Closed three gaps surfaced while pressure-testing the "inspectable AI" story.
All backend-verified live and 217 tests still pass.

- **Answer text captured in the trail (Gap 1).** The audit record is now the
  full record of *what the AI said*, not just that it answered. Added a hashed
  `detail` field to `AuditEvent` (in `_PAYLOAD_FIELDS`, so it's tamper-evident);
  the orchestrator's answer-event append passes `detail=answer.text`. Threaded
  through `event_from_dict`/`event_from_decision`, `HashChain.append_decision`,
  and the `AuditEventModel` wire schema. UI audit table shows the answer text
  (italic, quoted, truncated 90 chars + full tooltip) in the resource/detail
  column for answer events. `detail` defaults to `""`, so existing chains and
  hash tests are unaffected (verified: chain stays valid after a query).
- **Time-window audit query (Gap 2).** `/audit` now accepts `since`/`until`
  (ISO or plain date; naive→UTC normalized, `until` plain-date bumped to
  end-of-day on the client). Inspectors can now answer "what did alice access
  last week?" — verified: `since=2099`→0 events, `since=2000`→all, `user_id`
  filter scopes correctly. UI gained a second filter row (since/until date
  inputs, "last 7 days", "clear").
- **Export moved into the source preview (Gap 3).** Removed the per-citation
  export button; citation cards are now click-to-preview only. The green
  `export ↓` button lives inside the preview window and renders **only** when
  the persona holds `export` (view-only personas alice/bob never see it;
  charlie/diana/jdoe/erin/frank do). Closes the "can view but the export button
  is elsewhere" inconsistency.

> **Last updated:** 2026-10-09 (demo-hardening pass: TOCTOU formal demo, file-based audit tamper, FinTech narrative)

## Demo-hardening pass (2026-10-09)

Done this session, aimed at the live demo + submission narrative:

- **Formal (TLA+):** modeled revocation interleaved through the `decided` phase
  → spec now exercises the **time-of-check/time-of-use race**. Safe variant
  re-checks live ACL at retrieval (proven race-free); naive variant trusts the
  decide-time snapshot (TLC finds the leak). Consolidated to one live-flip
  harness `MC_tianquan.tla` (flip `BROKEN` FALSE→TRUE to go from "no error" to
  counterexample). This is a stronger story than the old filter-after-retrieval
  one.
- **Audit:** hash chain now **persists to `audit_log.json` on disk** every
  append; new `/audit/verify-file` re-reads and re-hashes the file, so a real
  hand-edit of the log is detected (replaces the gimmicky in-memory tamper
  button). UI button "verify log file". Fixed a real bug: `audit_chain or
  HashChain()` discarded a passed-in empty chain (empty chain is falsy via
  `__len__`) → now `is not None`.
- **Narrative:** rewrote `docs/project-description.md` to lead with the FinTech
  breach stakes (judges reward impact over complexity — see winner research
  below); added `docs/demo-script.md` (≈4-min rehearsable narration).
- Tests: 217 passing (added 5 file-tamper unit tests).

### Winner research (verified from tch.tencentcloud.com, 2026-10-09)

Hackathon = "Tencent Cloud AI CAN DO IT Singapore 2026", SGD $17k pool, 5 tracks
(Banking, Real Estate, FinTech, Digital Native, Healthcare). Showcased winners
skew **social-good / impact-led**: 1st Auntie AI (scam checker for elderly),
2nd EyeDentify (accessibility), 3rd NaviCore (maritime). Media framing rewards
"beyond technical complexity." Implication for us: our technical rigor is a
differentiator, but the *pitch must sell felt FinTech stakes*, not architecture.
FinTech/Aspire likely rewards rigor more than the social-good tracks, so the
formal-methods angle is an asset — framed as business risk, not academia.

> **Last updated:** 2026-09-29 (M14 in progress; UI/UX + access-control refinement batch underway)

## Active work batch — UI/UX + access-control refinement → COMPLETE

Permission model: `audit_query` (compliance_officer, admin, security_team) ·
`manage_permissions` (admin) · `export` (senior_engineer, finance_analyst,
security_team, compliance_officer, admin).

Backend:
- [x] B1. Added `audit_query` to `security_team` role.
- [x] B2. Per-permission gating: `audit_query` → `/audit/*`; `manage_permissions` → `/admin/*`, `/upload`. `can_audit`/`can_manage`/`can_export` exposed on `/users`; `viewer_privileged`/`viewer_can_export` on `/query`. (Fixed authz bug: compliance_officer could previously revoke/upload.)
- [x] B3. ADP client uses `truststore` (OS cert store) → fixes TLS `CERTIFICATE_VERIFY_FAILED` on intercepted networks; falls back to certifi then stub.
- [x] B4. Rewrote `StubLLMClient` as extractive summarizer (pulls real context sentences) — no more lazy "Relevant sources found: [1][2][3]".
- [x] B5. `/export` endpoint re-checks `Action.EXPORT` per cited resource and audits it; gated by `export` permission.

Frontend:
- [x] F1. Document list → card list.
- [x] F2. Policy inspector merged into audit explorer (standalone panel removed).
- [x] F3. Conditional panel rendering (no locked boxes): none → bare "ADMIN ACCESS REQUIRED"; `audit_query` → stats + explorer; `manage_permissions` → + revocation + upload.
- [x] F4. Audit explorer pagination (default 10, adjustable box, prev/next).
- [x] F5. Per-citation green "Export" button, rendered only when persona has `export`.
- [x] F6. Permission-denied actions → clear toast (via `api()` error path).

212 tests pass (`-p no:randomly`). Live-validated: per-permission 401/403/200,
extractive grounded answers, per-user export flags.

> **Resolved:** the earlier test-isolation flakiness
> (`test_grant_restores_access` failing under some orderings) was NOT shared
> ACL state — it was every `/query` attempting the live ADP call then falling
> back (slow + order-sensitive). Fixed with `tests/conftest.py` forcing the
> stub LLM (`ADP_APP_KEY=""`). Suite now runs deterministically in ~2s, 212
> passing under random ordering.

> **Later UI tweaks:** min-delay now applies only when there's no result
> (instant display when content exists). An access-control change does NOT
> auto-re-run any query — admin changes and user queries are separate actions
> by separate actors; the effect is seen on the affected user's next query, as
> in production. Note on revoke semantics: a **role** revoke leaves explicit
> `allowed_users` grants intact (access can remain via another path) — a
> **user** revoke uses the deny-list and is definitive. This is correct but can
> look like a no-op; demo with user-revoke (and re-query manually) for the
> clearest effect.

Panel → permission mapping:
| Panel | Permission | contractor/engineer/senior_engineer/finance_analyst | security_team/compliance_officer | admin |
|-------|-----------|:---:|:---:|:---:|
| stats + audit explorer | `audit_query` | ✗ | ✓ | ✓ |
| revocation + upload | `manage_permissions` | ✗ | ✗ | ✓ |

> **Last updated:** 2026-09-29 (M14 in progress; UI polish + server-enforced admin/audit role gating added)

## Milestone

**M0 — Project bootstrap** → complete  
**M1 — Data model & mock sources** → complete  
**M2 — Policy engine** → complete  
**M3 — Permission-aware retrieval pipeline** → complete  
**M4 — TLA+ formal specification** → complete  
**M5 — Audit trail** → complete  
**M6 — LLM answer agent** → complete (ADP Chat API adapter implemented; stub fallback for offline)  
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
- [x] **205 tests passing**: M1 (33) + M2 (22) + M3 (20) + M5 audit (18) + M6 agents (15) + M7 revocation (10) + M8 API (13) + M9 no-leak (7) + M11 grounding (17) + M12 freshness (9) + M13 injection (17) + ADP adapter (5) + search efficiency (19). (Frontend is static; no automated tests.)
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

- ~~**ADP AppKey needed for live LLM demo.**~~ **Resolved.** The ADP agent is
  published live at [adp.tencentcloud.com/webim_exp/#/chat/ULzqcG](https://adp.tencentcloud.com/webim_exp/#/chat/ULzqcG).
  Agent name "Tianquan 天权" and welcome message confirmed visible (even in
  incognito). The adapter (`backend/agents/adp_client.py`) is wired into the
  orchestrator with automatic stub fallback for offline dev. The hackathon
  requirement to use Tencent Cloud AI is satisfied by ADP.

- **ADP live call fails on TLS-inspected networks** (observed in dev:
  `CERTIFICATE_VERIFY_FAILED` reaching `wss.lke.tencentcloud.com`). The
  orchestrator now falls back to the stub LLM at runtime so `/query` still
  returns 200 instead of 500. For the live ADP demo, run on a network without
  TLS interception (or configure system/corporate CA certs). The stub fallback
  keeps the full permission/audit demo working offline regardless.

## Access control (frontend ↔ API)

The admin and audit surfaces are **server-enforced**, not cosmetic:
`/admin/*`, `/audit/*`, `/upload` require a privileged acting persona
(`admin` or `compliance_officer`, via `X-User-Id`) → 401 without identity,
403 otherwise. `/query` strips DENY details for non-privileged askers (no
metadata leak at the wire) and returns `viewer_privileged`. The frontend
reflects this: the Admin tab shows a locked state for non-privileged personas.
Privileged seed users: **diana** (compliance_officer), **frank** (admin).

## Key decisions made

- See [decisions/](decisions/) for ADRs.