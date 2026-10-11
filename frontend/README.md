# Frontend — Tianquan 天权

The Tianquan (天权) dashboard: query console with cited answers, source
preview, audit explorer, revocation controls, and permissions inspector.
CRT/phosphor-terminal styling generated with **Miora**, then wired to the
backend API.

## What it is

A **static** single-page app (no build step): `index.html` + `app.js`. Miora
produced the HTML/styling; `app.js` wires every panel to the FastAPI backend
(see [MIORA_PROMPT.md](MIORA_PROMPT.md) for the prompt and
[openapi.json](openapi.json) for the API contract).

Tailwind's browser build is **vendored and pinned** in `vendor/`
(`tailwindcss-browser-4.3.3.js`, MIT — see `vendor/tailwindcss-LICENSE.txt`),
so the page renders with no internet access. Icons are inline SVG.

## Files

- `index.html` — layout + CRT styling (from Miora), with hooks/IDs for wiring.
- `app.js` — API client + rendering. `API_BASE` constant points at the backend.
- `vendor/` — pinned Tailwind browser build + its licence.
- `MIORA_PROMPT.md` — the prompt used to generate the UI.
- `openapi.json` — exported backend API spec.

## Panels

Panels render only for personas holding the matching permission (enforced
again on the server).

- **Persona switcher** — seed users from `GET /users`; selection drives every
  request (sent as the `X-User-Id` header). Switching persona clears the
  previous answer.
- **Query console** — `POST /query`; the answer's `[n]` markers are buttons
  that jump to their citation card. A note appears when the grounding check
  removed unsupported sentences.
- **Source preview** (`export`) — click a citation or `[n]` to load the raw
  source via `GET /resource/{id}` (audited), with its origin link and a
  **download ↓** (`POST /export`).
- **Audit explorer** (`audit_query`) — plain-English search
  (`GET /audit/search`) and structured filters (`GET /audit`). Events are
  grouped per query under a header row with the question, UTC time, and
  allow/deny counts. Plain-English search fills the filter fields with what
  it understood. Revokes/grants appear as **CHANGE** rows. The integrity badge
  is re-checked on every refresh — including the on-disk log — so a hand-edit
  shows the moment you return to the page.
- **Access control** (`manage_permissions`) — `POST /admin/revoke|grant`. No
  auto re-run: the affected user sees the change on their next query.
- **Permissions inspector** (`manage_permissions`) — who can access what, by
  user, role, or resource (`GET /admin/permissions/*`). The refresh button reloads
  the resource options and selected lookup.

## Accessibility

- **clean mode** (header toggle) turns off the scanlines, glow, and blinking
  cursor and switches to a larger sans-serif type; the choice is remembered
  per browser. CRT styling stays the default.
- Visible keyboard focus everywhere; the persona switcher is a listbox (arrow
  keys, Enter, Escape); tabs follow the ARIA tab pattern; citation cards are
  keyboard-operable.
- Answers are announced to screen readers (`aria-live`); form
  fields have labels; the minimum text size is 11px; text colours meet WCAG AA
  contrast on their backgrounds; animations stop under
  `prefers-reduced-motion`.

## Running

1. Start the backend (from the repo root):

   ```powershell
   uvicorn backend.api.app:app --port 8000
   ```

2. Serve this folder over HTTP (not `file://`, since `app.js` calls the API
   cross-origin):

   ```powershell
   # from the frontend/ directory
   python -m http.server 5500
   ```

   Then visit `http://127.0.0.1:5500/`. (CORS is open on the backend, so any
   local port works.)

If the backend is not running, the footer shows `api: offline` — the UI degrades gracefully.

## Notes

- If you change `backend/api/schemas.py`, re-export the spec:
  `python -c "import json; from backend.api.app import create_app; open('frontend/openapi.json','w').write(json.dumps(create_app().openapi(), indent=2))"`
- The editor may warn `Unknown at rule @theme` in `index.html` — that's
  Tailwind v4's browser-build syntax; it's valid at runtime and can be ignored.
