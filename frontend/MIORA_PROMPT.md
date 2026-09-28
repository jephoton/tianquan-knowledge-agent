# Miora Prompt — VeriBrain Frontend (M8)

This is the prompt to give Miora to generate the VeriBrain React UI. It codes
against the FastAPI backend in `backend/api/` (see the API contract at the
bottom, and interactive docs at `http://localhost:8000/docs` while the server
runs).

## Before prompting

- Start the backend: `uvicorn backend.api.app:app` (default port **8000**).
- CORS is already open (`allow_origins=["*"]`), so the dev frontend can call it
  from any port.
- If Miora can import an OpenAPI spec, feed it `frontend/openapi.json`
  (exported from `GET /openapi.json`) so generated types match exactly.
- Miora generates **UI only** — it does not touch the backend. The REST API is
  the contract.

---

## The prompt

Build a React + TypeScript single-page dashboard called **VeriBrain** — a
permission-aware enterprise knowledge assistant. It talks to a local REST API
at `http://localhost:8000`. Use a clean, professional enterprise look (a
security/compliance console): neutral background, card-based layout, clear
ALLOW/DENY color coding (green/red), monospace for hashes and IDs.

**Layout: a top persona bar + three main panels.**

**1. Persona switcher (top bar).** On load, `GET /users` returns an array of
`{ user_id, name, roles: string[], department, is_contractor }`. Render these
as selectable chips/dropdown. The selected `user_id` is used for all queries.
Show the selected user's name, role, and a "Contractor" badge if
`is_contractor`.

**2. Query console (left/main panel).** A text input + "Ask" button. On submit,
`POST /query` with body `{ user_id, question, k: 20 }`. The response is:

```ts
{
  query_id: string,
  answer: string,
  no_access: boolean,
  citations: { marker: string, resource_id: string, source: string, title: string }[],
  decisions: { user_id: string, resource_id: string | null, action: string,
               result: "allow" | "deny", reason: string,
               acl_version: number, policy_version: number }[],
  allow_count: number,
  deny_count: number,
  audit_chain_head: string
}
```

Render the `answer` prominently. Below it, list `citations` as cards showing
`marker`, `source` (badge: confluence/jira/slack/gdrive), and `title`. If
`no_access` is true, show the answer text in a neutral "no results" style (not
an error).

**3. Policy inspector (right panel).** Render the `decisions[]` array from the
last query as a list of cards. Each card: `result` as a colored ALLOW (green) /
DENY (red) pill, the `resource_id` in monospace, the `reason`, and
`ACL v{acl_version}`. Show a summary header: "{allow_count} allowed ·
{deny_count} denied".

**4. Audit explorer (tab or bottom panel).** `GET /audit` returns:

```ts
{
  count: number, allow_count: number, deny_count: number,
  chain_valid: boolean, chain_status: string,
  events: { event_id: string, timestamp: string, user_id: string,
            query_id: string, resource_id: string | null, action: string,
            decision: string, reason: string, acl_version: number,
            policy_version: number, previous_hash: string,
            event_hash: string }[]
}
```

Show a tamper-evidence badge driven by `chain_valid` ("Chain verified" green /
"TAMPERED" red) using `chain_status` as tooltip. Render `events` as a table
(timestamp, user, resource, decision pill, reason, acl_version). Add filter
inputs that map to query params: `user_id`, `resource_contains`, `decision`
(allow/deny). Add a "Verify chain" button calling `GET /audit/verify` →
`{ valid: boolean, reason: string, broken_at_index: number | null, length: number }`.

**5. Revocation demo control (policy inspector or a small admin drawer).** A
form: resource_id, subject, subject_kind (user|role). "Revoke" →
`POST /admin/revoke`, "Grant" → `POST /admin/grant`, body
`{ resource_id, subject, subject_kind }`. Response:
`{ resource_id, previous_version, new_version, version_transition, change, subject, subject_kind }`.
After a revoke/grant, show a toast with `version_transition` (e.g. "v1 → v2")
and auto-re-run the last query so the user sees the citation disappear/reappear
live.

**Errors:** `POST /query` and `/admin/*` can return 404 with
`{ detail: string }` — show as a toast.

Provide a small typed API client module, use fetch, and make the base URL a
constant. No auth headers needed.

---

## Endpoint reference (source of truth: `backend/api/`)

| Method | Path | Purpose |
|--------|------|---------|
| GET  | `/health` | Liveness check. |
| GET  | `/users` | Seed personas for the switcher. |
| POST | `/query` | Ask a question as a user; returns answer + citations + decisions. |
| GET  | `/audit` | Filter the audit chain (`user_id`, `resource_contains`, `query_id`, `decision`, `action`). |
| GET  | `/audit/verify` | Chain integrity / tamper-evidence. |
| POST | `/admin/revoke` | Revoke a user/role from a resource (Demo 3). |
| POST | `/admin/grant` | Grant a user/role to a resource. |

## Demo mapping

- **Demo 1 (allowed, multi-source):** query as `alice` → answer with citations,
  policy inspector shows ALLOWs + some DENYs.
- **Demo 2 (no metadata leak):** query as `bob` about the security breach →
  `no_access: true`, neutral message, empty citations.
- **Demo 3 (live revocation):** revoke, watch `version_transition` and the
  citation disappear on auto-re-run.
- **Demo 4 (audit inquiry):** audit explorer filtered by user/resource.
- **Demo 5 (formal verification):** shown separately from TLC output, not in UI.

## Suggested seed personas

- `alice` — engineer (broad allowed access)
- `bob` — contractor (denied most restricted content)
- `charlie` — security_team (sees confidential security content)
- `diana` — compliance_officer (audit inquiries)
