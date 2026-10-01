# Frontend — Tianquan 天权

The Tianquan (天权) dashboard: query console, policy inspector, audit explorer, and
revocation controls. CRT/phosphor-terminal styling generated with **Miora**,
then wired to the backend API.

## What it is

A **static** single-page app (no build step): `index.html` + `app.js`, using
Tailwind via CDN. Miora produced the HTML/styling; `app.js` wires every panel
to the FastAPI backend (see [MIORA_PROMPT.md](MIORA_PROMPT.md) for the prompt
and [openapi.json](openapi.json) for the API contract).

## Files

- `index.html` — layout + CRT styling (from Miora), with hooks/IDs for wiring.
- `app.js` — API client + rendering. `API_BASE` constant points at the backend.
- `MIORA_PROMPT.md` — the prompt used to generate the UI.
- `openapi.json` — exported backend API spec.

## Panels

- **Persona switcher** — loads seed users from `GET /users`; selection drives all queries.
- **Query console** — `POST /query`; shows the grounded answer + citations.
- **Policy inspector** — ALLOW/DENY cards with reason + ACL version, from the query's `decisions[]`.
- **Audit explorer** — `GET /audit` with filters + tamper-evidence badge (`GET /audit/verify`).
- **Revocation controls** — `POST /admin/revoke|grant`; auto re-runs the last query so the change is visible live (Demo 3).

## Running

1. Start the backend (from the repo root):

   ```powershell
   uvicorn backend.api.app:app --port 8000
   ```

2. Open the UI. Because `app.js` calls the API cross-origin, serve the file
   over HTTP rather than opening it as a `file://` path:

   ```powershell
   # from the frontend/ directory
   python -m http.server 5500
   ```

   Then visit `http://localhost:5500/`. (CORS is open on the backend, so any
   local port works.)

If the backend is not running, the footer shows `api: offline` and a toast
appears — the UI degrades gracefully.

## Notes

- If you change `backend/api/schemas.py`, re-export the spec:
  `python -c "import json; from backend.api.app import create_app; open('frontend/openapi.json','w').write(json.dumps(create_app().openapi(), indent=2))"`
- The editor may warn `Unknown at rule @theme` in `index.html` — that's
  Tailwind v4's CDN syntax; it's valid at runtime and can be ignored.
