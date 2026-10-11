# Current State — Tianquan 天权

> **Last updated:** 2026-10-11 (independent review fixes: cross-platform search, preview audit, grounding, ADP isolation, audit question + grouping, accessibility, vendored assets, architecture diagram)

## Demo polish and continuation review

<!-- Generated continuation handoff. -->
- Removed popup toasts without adding replacement messages, per user preference. Existing query errors, ACL success status, inspector lookup errors, integrity badge and offline footer remain.
- Permissions inspector has a manual refresh button that reloads resource options and the selected lookup, and disables during requests. Its header button reuses the audit explorer’s `outline-btn` styling and dimensions.
- Verification: `uv run --with-requirements requirements.txt python -m pytest -q` → 289 passed (one dependency deprecation warning); `node --check frontend/app.js` passed. Targeted Node checks verified inspector refresh after revocation, updated resource options and failure recovery. Full browser rehearsal remains pending.

## Append-only audit log, fail-closed connectors, export/connector beats (2026-10-11, pass 4)

- **The audit log is append-only JSON Lines (`audit_log.jsonl`).** It used to
  rewrite the whole file from memory on every append, which silently "healed"
  a hand-edit on the next query. Now each event is one appended line; earlier
  lines are never rewritten, so tampering stays detectable after later
  queries. `verify_file()` also compares the file with the in-memory chain, so
  deleting the newest lines is caught as a truncated log.
- **Fixed a fail-open permission bug:** sources without their own rules (the
  upload connector) hit `unknown_source_default_allow` and skipped the ACL —
  an upload restricted to `security_team` was shown to alice. They now get a
  generic fail-closed ACL check (deny-list → user grant → role grant → deny).
- Demo script: new §5 (reading vs exporting) and optional §8 (plugging in a
  new source live via `/docs` → POST /upload); ≈7 min + reflection.
  289 tests pass.

## Audit explorer UX from demo run-through (2026-10-11, pass 3)

- **Permission changes are audited.** Revoke/grant append an `acl_revoke` /
  `acl_grant` event (actor, resource, `revoke role:engineer · ACL v1 -> v2`,
  decision `change` — never counted as allow/deny). Shown as amber CHANGE rows.
- **Integrity is checked automatically.** Every `/audit` and `/audit/search`
  verifies the in-memory chain **and** the on-disk file, so a hand-edit (or a
  deleted file) shows on the next refresh whatever the filters; the "verify
  integrity" button is gone. The UI also refreshes when the window regains
  focus and toasts once when tampering is first detected. An empty trail (no
  file yet) reads as verified.
- **Plain-English search fills the filter fields** (`filters` in the
  response: user_id, decision, resource, since, until); the table is loaded
  from those fields so it always matches them. The bracketed parameter echo is
  gone. The resource filter accepts comma-separated alternatives.
- **Prompt-injection attempts are flagged in the audit explorer** (red badge on
  the query group, read from the answer event's `injection_suspected:` reason).
- Demo script: first person ("I"), TLC commands inline, injection and
  permissions-inspector beats added; runbook updated.
  284 tests pass.

## Citation map in the audit trail + tool credits (2026-10-11, pass 2)

- **The logged answer's [n] markers are now traceable.** The answer event
  carries a hashed `citations` field (`[{"marker": "[1]", "resource_id": …}]`,
  only citations that passed INV6), so editing which document was cited is
  detected. The audit explorer shows a `cited:` key under the answer
  (hover a chip for its document) and marks each allowed row `citation [n]` or
  `not cited` — what the model was given vs what it used. 275 tests pass.
- **Tencent tools credited** in the project description, README and a video
  reflection section in the demo script: CodeBuddy (planning + core build),
  ADP (every LLM answer, filtered context only, no knowledge base), Miora (UI
  design + cover image).
- ADP knowledge base removed by the owner (2026-10-11). Cover image done
  (Miora, 1672×941, 16:9) and uploaded to the submission (2026-10-11).

## Independent review fixes (2026-10-11)

An end-to-end review against the handbook found demo-breaking bugs; all fixed
with regression tests. **273 tests pass.** Live-verified against ADP.

- **Cross-platform search restored (ADR-0006).** Naming a platform ("…raised
  in Slack?") used to restrict search to that one source, so the demo question
  returned one Slack thread, no Jira/Confluence and no denials. Now a named
  platform is a 2× ranking boost. Demo question: **8 allow / 2 deny**
  (`confluence:q3-breach-report`, `SEC-101`) across 4 sources.
- **ADP calls are stateless (ADR-0007).** The shared ADP client reused one
  `ConversationId`, so the model remembered other users' prompts (an INV2
  break, caught only by the grounding checker). Each call now opens a fresh
  conversation. Also: the SSE stream is decoded as UTF-8 (em dashes and
  Chinese were garbled).
- **Source preview is a proper boundary.** `GET /resource/{id}` took the user
  from a `?user_id=` query param (any caller could read as anyone), wrote no
  audit event, and returned 403 vs 404 (an existence oracle). Now: identity
  from `X-User-Id`, requires `export` (server-side, matching the UI), every
  view audited (`detail="source_preview"`), denied ≡ not found (same 404).
- **Grounding over-strip fixed.** Sentence-opening words ("Based", "There",
  "Both") were treated as named entities, so correct ADP sentences were cut.
  Phrases and hyphenated terms are now checked word by word; month names match
  ISO dates; "9 AM" matches "9AM"; `[n]` digits aren't numbers. 0 removals
  across 6 live samples. `/query` returns `grounding_removed`, shown in the UI.
- **Question captured in the audit trail.** New hashed `question` field on
  every event of a query (the handbook requires "query + retrieved doc IDs +
  final answer"). Editing it in the file is detected.
- **Plain-English audit search resolves resources.** Phrases like "the q3
  breach report", "the ENG confluence space", "the SEC project", "in jira"
  resolve against the live catalog (`resource_ids` filter); words it can't map
  are reported in `unparsed` and shown in amber. The handbook example's
  nonexistent `payment-gateway` space is reported, with a fallback to
  Confluence pages about it.
- **UI:** inline `[n]` markers jump to (and, with `export`, open) the cited
  source; the preview shows the source's origin URL; the audit table groups
  events under one header row per query (question, UTC time, allow/deny
  counts) and paginates by query.
- **Accessibility:** clean-mode toggle (no CRT effects, larger sans-serif,
  remembered per browser); visible focus; keyboard persona listbox; ARIA tabs;
  `aria-live` answers/toasts; labelled fields; min 11px text; two text colours
  raised to WCAG AA; `prefers-reduced-motion` respected; page `<title>`.
- **Vendored assets:** Tailwind browser 4.3.3 pinned in `frontend/vendor/`;
  Font Awesome and Lucide removed (two inline SVG icons). The UI renders with
  no internet access.
- **Docs:** architecture diagram (`docs/architecture.svg` + `.png`),
  architecture.md rewritten, ADR-0006/0007, demo runbook/script, READMEs,
  project description, ADP plan (no knowledge base), `openapi.json` re-exported.

### Open items (need you)

- ~~ADP agent knowledge base~~ — removed (2026-10-11).
- ~~Cover image~~ — done (Miora, 16:9) and uploaded (2026-10-11).
- **Demo video** (5–8 min, optional but how preliminary judges see the demo);
  the demo script is ~4 min, and the video should include a short reflection
  on building with CodeBuddy.
- Revoke form's resource field is still free text (the permissions inspector
  covers before/after lookups).


## Removed upload UI, added permissions inspector (2026-10-10, pass 5)

- **Removed the document-upload panel from the UI.** It read as a debugging
  side-door, not a connector — and the thesis is permission-aware retrieval over
  *existing* systems (Confluence/Jira/Slack/GDrive). The clunky
  upload-then-grant-in-another-panel workflow reinforced that. The backend
  `UploadConnector` and `/upload` routes are KEPT (unsurfaced) — they prove the
  system is connector-extensible via one `BaseConnector` interface, which is a
  pitch/architecture point, not a UI feature.
- **Added a permissions inspector** in the freed space (`backend/policy/
  inspector.py` + `/admin/permissions/*` endpoints, gated by
  `manage_permissions`). Three read-only lookups, all computed by evaluating the
  *real* PolicyEngine (not raw ACL membership), so what it shows is exactly what
  a query could retrieve:
  - **by user** → every resource, can_read/can_export, and *how* access is
    granted (user-grant vs role:<name> vs denied/no-match); also lists the
    user's roles.
  - **by role** → member users + resources the role grants.
  - **by resource** → raw ACL (allowed_users/roles, denied_users) + the
    *effective readers* (who the engine actually allows).
  12 inspector unit tests. Live-verified the demo loop: revoke `engineer` from
  db-migration-plan → alice drops out of `effective_readers` (frank, jdoe
  remain) → grant restores. 244 tests pass.

## Preview-panel presence model + query-clear on switch (2026-10-10, pass 4)

- **Source-preview panel is now presence-gated, not click-gated.** The panel is
  always present (showing an empty "click a cited source…" ready state)
  whenever the persona holds `export`, and absent entirely otherwise — it no
  longer only appears after a click. Clicking a citation swaps the empty state
  for the populated content (+ download + close); close returns it to the empty
  state (panel stays). `syncPreviewPanel()` runs on every persona switch.
- **Account switch clears the query session.** `clearQuery()` resets the input,
  answer, and citations on persona switch (results belong to the persona that
  ran them) and resets the preview to its empty state.
- **Note on INV8 stripping (clarification, not a change):** the grounding
  checker still strips ungrounded sentences in the normal (partial) case — only
  the *total-strip* edge case was changed in pass 3 to keep the
  citation-validated text instead of a placeholder. INV8 is fully intact.

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
- Demo 1 (alice): 8 allow / 2 deny across 4 sources (re-verified 2026-10-11 after the search fix).
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
- ~~Cover image (M15 #5)~~ — done (Miora, 16:9), uploaded 2026-10-11.
- **Demo video** (M15 #6, 5–8 min) — optional, but it is how preliminary
  judges see the demo.

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

The admin, audit and raw-source surfaces are **server-enforced**, not
cosmetic (acting persona via `X-User-Id`; 401 without identity, 403 without
the permission):

| Routes | Permission | Seed personas |
|---|---|---|
| `/audit/*` | `audit_query` | charlie (security_team), diana (compliance_officer), frank (admin) |
| `/admin/*`, `/upload` | `manage_permissions` | frank |
| `/resource/{id}`, `/export` | `export` | charlie, diana, jdoe, erin, frank |

`/query` strips DENY details for callers without `audit_query` (no metadata
leak at the wire). The frontend hides the tab bar entirely for personas with
no admin access and renders each panel only with its permission.

## Key decisions made

- See [decisions/](decisions/) for ADRs.