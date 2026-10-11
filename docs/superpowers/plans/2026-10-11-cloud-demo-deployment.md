# Cloud Demo Deployment — Implementation Handoff

<!-- Generated plan, 2026-10-11. No deployment or application changes executed. -->

**Status:** Plan only. The user explicitly requested no implementation yet and intends to hand this to another agent. Execute only after the user authorizes implementation/deployment. Do not create services, provision paid resources or publish changes during a documentation-only handoff.

**Goal:** Host Tianquan's static UI on Vercel and its existing FastAPI backend on a cloud web service, so the laptop can be off while judges use the demo.

**Architecture:** One backend process/worker/instance retains the current in-memory seed connectors, ACL changes, uploads and audit chain during its lifetime. Vercel serves static assets and public API-origin configuration. The backend alone calls ADP. Restart resets demo state and truncates the audit log. This plan intentionally requires no shared database or storage migration; see [ADR-0009](../../decisions/0009-cloud-demo-with-process-local-state.md).

**Tech stack:** Existing Python/FastAPI and pinned requirements; static HTML/JS with vendored Tailwind; a small Node build script for frontend runtime config. Render is the proposed backend host, not an already selected/provisioned account. An equivalent long-running host can use the same start command and one-instance constraints.

## Read before executing

- [Current state](../../current-state.md), [architecture](../../architecture.md), [demo runbook](../../demo-runbook.md).
- `backend/api/app.py`, `backend/api/state.py`, `backend/audit/hash_chain.py`, `frontend/app.js`, `frontend/index.html`, `requirements.txt`, `.gitignore`.
- Baseline: 292 passing Python tests, no cloud frontend configuration yet, backend CORS allows all origins. Preserve the user-provided untracked `docs/cover_image.png`.
- The direct ADP experience URL is not the permission-aware app. Do not use it as the full app deployment URL.
- Demo personas are selectable by anyone; use synthetic data. One worker does not eliminate threaded-request races. Missing ACL fallback and all-rejected grounding fallback are known limitations recorded in current state. This deployment does not fix those gaps or claim production readiness.

## Hosting settings and tradeoff

[Render's FastAPI guide](https://render.com/docs/deploy-fastapi) supports a Python web service with a port-bound Uvicorn command. Proposed fields:

| Setting | Value |
|---|---|
| Repository | `jephoton/tianquan-knowledge-agent` |
| Branch | The reviewed deployment commit on `main` |
| Root | Repository root |
| Runtime | Python; use a supported Python 3.11 patch and verify it in build logs (baseline minor is 3.11) |
| Build | `pip install -r requirements.txt` |
| Start | `python -m uvicorn backend.api.app:app --host 0.0.0.0 --port $PORT --workers 1` |
| Instances/workers | Exactly one each; no autoscaling |
| Health path | `/health` |
| Backend secrets | `ADP_APP_KEY` in the service's secret environment |
| Audit path | `TIANQUAN_AUDIT_LOG=/tmp/tianquan-audit.jsonl` (deliberately ephemeral) |
| CORS | `TIANQUAN_ALLOWED_ORIGINS`: exact approved frontend origin(s) |

The start command above is for the Linux cloud runtime; PowerShell local commands still use `--port 8000`.

[Render free web services](https://render.com/docs/free) sleep after 15 idle minutes and lose local file changes on restart/redeploy/spin-down. Expect a cold start and a fresh demo state on wake. A paid service can reduce availability friction, but this application still resets state on restart. The user must choose the tier before any paid provisioning; do not promise free always-on service or add keepalive workarounds.

## Task 1 — Confirm boundaries and deployment access

- [ ] Inspect `git status`, local project instructions and the current handoff. Preserve unrelated assets/changes.
- [ ] Confirm the backend host/account and free versus paid tier with the user; explain the documented cold-start/reset behavior if a tier is not already chosen. Existing authorization can be reused.
- [ ] Inspect Vercel project linkage and backend service linkage; reuse suitable projects rather than creating duplicates. Check `gh auth status` before any push and use `jephoton`.
- [ ] Record any host-specific Python version pin in its configuration and verify the installed minor in build logs. Do not upgrade dependencies as part of deployment.

No code commit for this inspection task.

## Task 2 — Configure the static frontend API origin

**Modify:** `frontend/app.js`, `frontend/index.html`, `.gitignore`, `frontend/README.md`.
**Create:** `frontend/config.js`, `frontend/scripts/build.cjs`.

- [ ] Add a local-safe public default config:

```javascript
// frontend/config.js
window.TIANQUAN_CONFIG = { apiBase: "http://localhost:8000" };
```

- [ ] Load `config.js` immediately before `app.js` in `index.html`:

```html
<script src="config.js"></script>
<script src="app.js"></script>
```

- [ ] Replace only the hardcoded API origin in `app.js`:

```javascript
const API_BASE = (window.TIANQUAN_CONFIG?.apiBase || "http://localhost:8000").replace(/\/+$/, "");
```

Keep every existing route and button behavior. API configuration must contain no key/token.

- [ ] Add this build script, which emits only UI assets and public configuration into `dist/`:

```javascript
// frontend/scripts/build.cjs
const fs = require("node:fs");
const path = require("node:path");
const root = path.resolve(__dirname, "..");
const out = path.join(root, "dist");
const raw = process.env.TIANQUAN_API_BASE;
if (!raw) throw new Error("Set TIANQUAN_API_BASE to the backend HTTPS origin");
const origin = new URL(raw);
if (origin.protocol !== "https:" || origin.username || origin.password ||
    origin.pathname !== "/" || origin.search || origin.hash) {
  throw new Error("TIANQUAN_API_BASE must be a bare HTTPS origin without credentials");
}
fs.mkdirSync(out, { recursive: true });
for (const item of ["index.html", "app.js", "vendor"]) {
  fs.cpSync(path.join(root, item), path.join(out, item), { recursive: true });
}
fs.writeFileSync(path.join(out, "config.js"),
  "window.TIANQUAN_CONFIG = " + JSON.stringify({ apiBase: origin.origin }) + ";\n");
```

- [ ] Ignore `frontend/dist/` in `.gitignore`; do not commit build artifacts. Leave the tracked local config unchanged during builds.
- [ ] Verify `node --check frontend/app.js`, `node --check frontend/scripts/build.cjs`; run the build with the real service origin when available. Before hosting, a synthetic `https://backend.example.com` origin can check output generation without a network request. Missing/HTTP/credential-bearing origins must fail the build.
- [ ] Serve `frontend/` locally and confirm it still targets localhost. Inspect emitted `dist/config.js` and assets before deploying; confirm no backend files or `.env` are included. Use a browser later to verify the actual API requests, not just the config text.

Atomic commit: `feat(deploy): configure frontend API origin for cloud hosting`.

## Task 3 — Restrict browser origins without changing demo auth

**Modify:** `backend/api/app.py`, `tests/test_api.py`, `backend/README.md`.

- [ ] Before `app.add_middleware`, parse configured origins:

```python
origins = [
    value.strip()
    for value in os.environ.get(
        "TIANQUAN_ALLOWED_ORIGINS",
        "http://127.0.0.1:5500,http://localhost:5500",
    ).split(",")
    if value.strip()
]
```

- [ ] Use `allow_origins=origins`, `allow_methods=["GET", "POST"]`, `allow_headers=["Content-Type", "X-User-Id"]`, `allow_credentials=False` in the existing CORS middleware. Preserve API authorization logic.
- [ ] Add meaningful preflight coverage: an allowed local/configured HTTPS origin receives matching `Access-Control-Allow-Origin`; an unlisted origin does not. Cover the `X-User-Id` header used by inspector/audit/export/admin requests. Set test origins via `monkeypatch` before `create_app()`.
- [ ] Run the complete suite with an isolated `TIANQUAN_AUDIT_LOG` as documented in [tests README](../../../tests/README.md). Tests must stay stubbed and not alter a running demo's audit file.
- [ ] Document that CORS is a browser restriction, not identity verification. Keep selectable personas for the synthetic demo; do not add SSO or rewrite policy.

Atomic commit: `fix(deploy): restrict API CORS to configured frontend origins`.

## Task 4 — Deploy the single backend

- [ ] Once implementation/deployment is authorized, create or update the chosen service using the settings above. Keep credentials in its secret environment and out of commands/logs/screenshots committed to Git.
- [ ] Configure one instance and `--workers 1`; verify build logs and `/health` over HTTPS. `/health` returning `adp` proves key presence only. Exercise an allowed query and inspect provider-side evidence if verifying actual live ADP use; fallback can otherwise mask failures.
- [ ] Capture the actual backend URL for frontend configuration. Do not invent a URL or claim deployment is complete on a successful build alone.
- [ ] Keep persistent disk/databases out of this change. Avoid reload mode and background state workers.

If a tracked host configuration is added, commit it independently as `chore(deploy): configure single-instance backend hosting`; it must contain no secret values. Otherwise record the service settings in the final deployment documentation.

## Task 5 — Deploy the static UI on Vercel

Use the [official Vercel build configuration](https://vercel.com/docs/builds/configure-a-build):

| Setting | Planned value |
|---|---|
| Repository | `jephoton/tianquan-knowledge-agent` |
| Root Directory | `frontend` |
| Framework | Other |
| Build Command | `node scripts/build.cjs` |
| Output Directory | `dist` |
| Install Command | No dependency install required |
| Public build variable | `TIANQUAN_API_BASE` = actual backend HTTPS origin |

- [ ] Set environment values for the intended deployment environment, deploy, then inspect the generated page/config and network requests. Never put `ADP_APP_KEY` on Vercel's frontend project.
- [ ] Add the exact final Vercel/custom-domain origin to backend `TIANQUAN_ALLOWED_ORIGINS`. Include preview origins only if explicitly needed, as exact origins. Do not allow `*.vercel.app` broadly.
- [ ] If the final Vercel origin is assigned only after the first deployment, configure it on the backend and redeploy/restart the backend. This resets state; repeat smoke checks afterward.
- [ ] Confirm judge access is possible without a hosting-account login. Inspect deployment protection settings before using the URL in the submission; public release must be within the user's deployment authorization.

## Task 6 — Verify the deployed demo end to end

Use synthetic data and the exact queries in the runbook. Record observations, not expected outcomes as evidence.

- [ ] Frontend loads via HTTPS, footer connects, assets have no failed requests, API calls use the cloud host (no localhost/mixed content).
- [ ] Alice's migration question returns cited allowed content. Diana sees the matching allow/deny audit group.
- [ ] Bob Q3: canonical no-access response, zero citations. Charlie repeats the same query, reads/previews/exports the Q3 report, then asks “Show me the Q5 report.” Q5 response equals Bob's message exactly.
- [ ] Frank revokes role `engineer` on `confluence:db-migration-plan`; inspector refresh updates and Alice's next query excludes that resource. Restore that grant after the check.
- [ ] Diana's audit search returns grouped events including preview/export and ACL changes; integrity verifies before any deliberate tamper test. Remote file editing is not needed to validate deployment.
- [ ] Check privilege gates with a nonprivileged persona, local frontend compatibility and allowed/blocked browser-origin behavior. Inspect browser console/network for errors.
- [ ] Restart the cloud service once and verify the documented clean seed state/empty audit behavior. On a free tier, also document cold-start behavior rather than calling the service always-on.
- [ ] Save any needed test evidence before the final reset. Return the demo to fresh seeded state before handing over the URL.

## Task 7 — Final handoff and rollback

**Modify:** `README.md`, `docs/current-state.md`, `docs/architecture.md`, this plan and relevant backend/frontend setup docs.

- [ ] Record actual public UI/backend URLs, selected host/tier, tested runtime, commands, final test count, observed smoke results and reset/cold-start behavior. Mark implementation tasks complete only when verified.
- [ ] Keep demo video/script and user assets intact. Do not reintroduce toasts, replacement status text, removed connector showcase or timing choices.
- [ ] Commit documentation separately: `docs(deploy): record cloud demo setup and verification`.
- [ ] For code rollback, redeploy the last reviewed application commit on both hosts and retest. Backend rollback/restart resets state; it cannot recover old ACL mutations/uploads/audit history. Do not delete cloud projects as a rollback shortcut.
- [ ] Check `gh auth status` before an authorized push. Report commits, URLs and material limits; do not claim production durability or a complete formal proof.

## Completion criteria

A judge can open the full UI while the laptop is off and exercise the recorded permission/demo paths. Frontend points to the real HTTPS backend, credentials remain backend-only, exactly one backend instance/worker runs, configured browser origins work, tests/smoke checks pass, and the handoff accurately states restart/reset and hosting limitations.
