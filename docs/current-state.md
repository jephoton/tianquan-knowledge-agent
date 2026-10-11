# Current State — Tianquan 天权

<!-- Generated handoff; verified against code and tests on 2026-10-11. -->

Read this first when continuing the project. [Architecture](architecture.md) describes the implementation, [decisions](decisions/) explain durable choices, and [roadmap](plan.md) tracks scope. Earlier implementation notes are preserved as [historical snapshots](history/implementation-notes.md).

## Status and next step

The demo video is complete, as reported by the user. Submission copy (blurb + project description, following the handbook's four required headings) is in [project-description.md](project-description.md); pasting it into the submission portal is the user's step. CodeBuddy usage evidence is summarised, with all five screenshots embedded, at the top of the [development log](dev-log/dev-log.md#codebuddy-usage-evidence). Remaining: hosting. Do not recreate the demo or assume older screenshot checklists are outstanding.

**Deployed 2026-10-11.** Frontend: https://tianquan.vercel.app (Vercel project `tianquan`, account `jettan17`; `frontend/vercel.json` + `scripts/build.cjs`, `TIANQUAN_API_BASE` passed as a build env). Backend: https://tianquan-api.onrender.com (Render free web service from `render.yaml`; `ADP_APP_KEY` and `TIANQUAN_ALLOWED_ORIGINS=https://tianquan.vercel.app` set in the dashboard). Verified in production: CORS allows only the Vercel origin; Alice's cited 4-source answer via ADP, Bob's denial, Charlie's Q3 report/preview/export, identical Q5 message, revoke → next-query exclusion (grant restored), audit groups/search/[VERIFIED], Bob 403 on /audit. Free tier sleeps after ~15 idle minutes (30–60 s cold start; state resets). Redeploy frontend: `vercel deploy --prod --cwd frontend --build-env TIANQUAN_API_BASE=https://tianquan-api.onrender.com`; backend: Render manual deploy (autoDeploy off). The plan below remains the reference. No database, Redis or shared-storage migration is required for this demo ([ADR-0009](decisions/0009-cloud-demo-with-process-local-state.md)). Backend host/plan and any paid provisioning remain to be selected.

## Implemented baseline

- Four mock platform connectors, 20 seed resources, seven personas, plus runtime uploads through the API.
- TF-IDF and character n-gram candidate search across sources. Platform mentions boost results rather than excluding other sources. Explicit Q-number labels match exact title/body tokens; Q5 cannot substitute Q3.
- Permission filtering before context assembly; supported connectors' current ACLs are fetched per candidate. Source rules, deny lists, sensitivity clearance and action permissions determine access.
- Live revoke/grant changes ACL versions and affects subsequent queries without reindexing.
- Tencent Cloud ADP adapter with a fresh conversation per call; extractive stub when no key is configured or a live call fails. No knowledge base should be attached to the ADP agent.
- Citation validation, lexical grounding checks, source timestamps and audit flags for suspicious prompt patterns. These are implemented checks, not a semantic proof of each answer.
- Audited raw-source viewing and export, with server-side role and resource permission checks.
- Hash-chained append-only `audit_log.jsonl`; structured and plain-English audit search, query grouping, logged answer/citation mapping, ACL change events and automatic file integrity verification.
- Static HTML/JS dashboard, vendored Tailwind, clean mode, keyboard navigation and persona-dependent panels. Popup toasts removed without replacement messages. Permissions inspector refresh uses the audit explorer button styling and reloads both resources and the selected lookup.
- TLA+ finite model with six active invariants (INV1–INV4, INV6, INV7). INV5 is deferred; INV8 is Python-only. The model does not formally verify the Python application.

## Verified commands

Run from the repository root with Python 3.11 and dependencies from `requirements.txt`:

```powershell
uv run --with-requirements requirements.txt python -m uvicorn backend.api.app:app --port 8000 --workers 1
```

In another terminal:

```powershell
python -m http.server 5500 --directory frontend
```

Open `http://127.0.0.1:5500/` and API docs at `http://127.0.0.1:8000/docs`. The UI reads its API origin from `frontend/config.js` (local default `http://localhost:8000`); the Vercel build writes the cloud origin.

For tests, isolate the log from an already running demo:

```powershell
$previousAuditPath = $env:TIANQUAN_AUDIT_LOG
$env:TIANQUAN_AUDIT_LOG = Join-Path $env:TEMP ('tianquan-tests-' + [guid]::NewGuid().ToString() + '.jsonl')
try {
    uv run --with-requirements requirements.txt python -m pytest -q
} finally {
    $env:TIANQUAN_AUDIT_LOG = $previousAuditPath
}
```

Fresh verification on 2026-10-11: **292 passed**, one FastAPI/Starlette dependency deprecation warning. `tests/conftest.py` forces the stub and ADP adapter tests mock HTTP; this suite does not prove the cloud deployment or live ADP availability. Historical live API checks covered Bob's Q3 denial, Charlie's Q3 citations/preview/export and identical missing-Q5 response.

TLC setup and safe/broken harness commands: [formal README](../formal/README.md). The demo opens `access_control.tla`, `MC_tianquan.tla`, `MC_tianquan.cfg` and prepared TLC output.

## State, reset and credentials

One process owns the identities, connectors, ACL mutations, uploads and audit chain. **Restarting resets ACLs/uploads and truncates the audit file**, even if that file is on a persistent disk. No startup recovery is implemented. Save evidence before resetting. Stop only the verified backend process or its own terminal, then rerun the backend command; the frontend does not need restarting.

`ADP_APP_KEY` belongs in the backend environment or ignored local `.env`, never frontend config or documentation. `TIANQUAN_AUDIT_LOG` overrides the writable log path. `/health` reports configured mode (`adp` when the key is present), not proof that a particular answer used ADP.

The [published ADP experience](https://adp.tencentcloud.com/webim_exp/#/chat/ULzqcG) is a direct model chat. It bypasses Tianquan's server permission/audit pipeline and is not the full application demo URL.

## Known boundaries and follow-ups

- Persona IDs are demo authentication: `/query` uses the body `user_id`; privileged endpoints resolve `X-User-Id`. Anyone reaching the demo can select seeded personas. Use synthetic data only; production needs verified identity.
- Run exactly one worker and one instance. Multiple workers split state and can truncate the same audit file. Threaded requests can still overlap within one worker; the audit chain has no synchronization. Avoid claiming concurrent production safety.
- When `get_acl()` returns `None`, `PermissionFilter._live_resource()` returns the indexed resource. The policy engine can permit that snapshot. This is a known gap for a disappearing/unavailable source; the current seeded connectors do not exercise it. Future real connectors must explicitly deny unavailable ACLs and add a regression test.
- ACL checks and subsequent context assembly are separate Python operations; TLA+ explores a bounded abstract revocation schedule, not all implementation interleavings.
- Content is indexed at initialization/reindex; only ACLs are refreshed per retrieval candidate. Citation freshness labels describe indexed source timestamps, not a guaranteed live content fetch.
- Grounding is lexical. If it rejects every sentence, the orchestrator restores the citation-validated original answer; this applies to live output as well as the stub. Do not claim every unsupported sentence is always removed.
- File verification detects edits/truncation relative to the running chain. It is not an externally anchored or durable regulatory ledger and does not survive restart.
- CORS is restricted to `TIANQUAN_ALLOWED_ORIGINS` (default: the local frontend). That is a browser restriction and does not replace authentication.
- Free backend hosting may sleep and reset the demo on wake. Visitors share mutable demo state; this is an accepted demo tradeoff.

## Demo decisions to preserve

Opening hook and formal-methods elevator pitch → architecture → first UI reveal/clean mode → Alice's unified answer → Bob's denial → Charlie repeats Bob's query, previews/exports, then asks for missing Q5 → revoke/inspector refresh → audit/tamper → TLA+ assurance (live mutation optional) → spoken feature recap → reflection last. New-source showcase and timing/recovery section were removed. Keep the user's intro/outro and current sequence when making future changes.

`docs/cover_image.png` is currently a user-provided untracked asset; leave it intact and do not include it in unrelated commits.
