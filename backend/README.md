# Backend — Tianquan 天权

<!-- Generated setup reference; reconciled on 2026-10-11. -->

Python/FastAPI service for permission-aware retrieval, cited answers and audit inspection. The [architecture](../docs/architecture.md) maps the modules and boundaries.

## Run locally

From the repo root with Python 3.11 and uv:

```powershell
uv run --with-requirements requirements.txt python -m uvicorn backend.api.app:app --port 8000 --workers 1
```

Alternatively install `requirements.txt` in a virtual environment and run `python -m uvicorn backend.api.app:app --port 8000 --workers 1`. API docs: `http://127.0.0.1:8000/docs`; liveness: `/health`.

- `ADP_APP_KEY`: backend-only environment variable or ignored `.env`; absent key uses the extractive stub. Live failures also fall back.
- `TIANQUAN_AUDIT_LOG`: writable JSONL path, default `audit_log.jsonl` in the working directory.
- `/health` reports configuration, not confirmation that every response used ADP.

## Configuration

| Variable | Purpose |
|---|---|
| `ADP_APP_KEY` | Tencent Cloud ADP key (backend only; `.env` locally, secret env in the cloud). Without it answers use the offline extractive fallback. |
| `TIANQUAN_AUDIT_LOG` | Path of the append-only audit log (default `audit_log.jsonl`). |
| `TIANQUAN_ALLOWED_ORIGINS` | Comma-separated exact browser origins allowed by CORS (default `http://127.0.0.1:5500,http://localhost:5500`). A browser restriction only — not identity verification. |

Cloud hosting: `render.yaml` (one free-tier instance, `--workers 1`); see the [deployment plan](../docs/superpowers/plans/2026-10-11-cloud-demo-deployment.md).

## Structure

| Directory | Responsibility |
|---|---|
| `api/` | Query, audit, admin, source preview/export and upload routes; process-local state |
| `connectors/` | Mock Confluence/Jira/Slack/Drive plus runtime upload connector |
| `auth/` | Seeded identities and role/action permissions; no production sessions/SSO |
| `policy/` | Policy decisions, source mapping, freshness, revoke/grant and inspector |
| `retrieval/` | Indexing, TF-IDF/n-gram search, ACL filter and context assembly |
| `agents/` | Orchestrator, ADP/stub, answer/citation checks, grounding and injection flags |
| `audit/` | Event schema, hash chain, file verification and audit search |
| `seed/` | Readable reference copy of the 20 synthetic documents (one `.txt` per resource). Not loaded at runtime — the connectors in `connectors/` embed the same text, which is what the app serves. |

## State and recovery

Use one worker and one instance. ACL mutations, uploads and audit memory are local to that process. Restart resets them and **truncates the audit file**; save needed evidence first. A persistent disk alone does not provide restart recovery. Stop the backend in its own terminal and rerun the command; leave the frontend running.

Tests must use a separate audit path when a demo is running: see [test instructions](../tests/README.md). Deployed on Render (`https://tianquan-api.onrender.com`, from `render.yaml`) behind the Vercel UI at https://tianquan.vercel.app; see the [deployment plan](../docs/superpowers/plans/2026-10-11-cloud-demo-deployment.md). Known ACL, concurrency and grounding gaps are in [current state](../docs/current-state.md#known-boundaries-and-follow-ups).
