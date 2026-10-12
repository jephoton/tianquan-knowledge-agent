# Architecture — Tianquan 天权

> **Last updated:** 2026-10-11

<!-- Generated reconciliation: implementation boundaries and deployment status. -->

![Tianquan architecture and trust boundaries](architecture.png)

The diagram source is [architecture.svg](architecture.svg) (renders on GitHub);
[architecture.png](architecture.png) is a 3200×2000 export for slides and the
submission form. To re-export after editing the SVG, open it in any browser at
1600×1000 and screenshot at 2× (e.g. headless Edge/Chrome with
`--force-device-scale-factor=2 --window-size=1600,1000 --screenshot`).

## 1. System overview

One request path, enforced in a fixed order:

1. **Web UI** (static HTML/JS) sends the question with the acting persona.
2. **FastAPI** resolves identity and applies server-side permission gates.
3. **Orchestrator** runs every query through:
   1. injection scan (flag only),
   2. candidate search over all four sources,
   3. **permission filter** — live ACL re-fetch + PolicyEngine, per candidate,
   4. context assembler (authorized content only, citation-marked),
   5. audit allow/deny decisions before generation,
   6. **Tencent Cloud ADP** drafts the cited answer (stub fallback available),
   7. answer checks — citation validation (INV6) and grounding (INV8),
   8. audit the served answer and citation map, hash-chained to disk.
4. Denied documents go to the audit log only — never to the LLM, never to the
   unauthorized asker. Authorized auditors can inspect denial metadata.

## 2. Trust boundaries

| | Boundary | What crosses it, and what may not |
|---|---|---|
| TB1 | **Identity at the API** | `POST /query` resolves the body `user_id`; privileged routes resolve `X-User-Id`. Both are caller-selected demo identities; production needs verified SSO/OIDC. Privileged routes return 401/403 server-side regardless of the UI. |
| TB2 | **Policy engine is authoritative** | The filter fetches current ACLs per candidate and runs the policy engine. Missing ACLs currently fall back to the indexed resource; see limitations below. |
| TB3 | **Only authorized content passes** | The context assembler only ever receives allowed resources. |
| TB4 | **LLM sees filtered context only** | ADP receives the assembled authorized context and nothing else. Each call opens a **fresh ADP conversation**, so the model has no memory of another user's prompt. |
| TB5 | **Every decision is logged** | Allow and deny decisions, the question, and the served answer are appended to a SHA-256 hash chain, appended to `audit_log.jsonl` (append-only: earlier lines are never rewritten, so a hand-edit stays detectable). |

The critical invariant across all boundaries:

> **The LLM never receives content the user is not authorized to see. Filtering
> happens before the LLM, not after.**

## 3. Module map

### `backend/connectors/`

Mock source-system connectors behind one `BaseConnector` interface
(`list_resources`, `get_resource`, `get_acl`, `check_membership`,
`update_acl`). Each preserves its source's native permission model:

| Source       | Permission model                              | Seed containers |
|--------------|-----------------------------------------------|-----------------|
| Confluence   | space visibility + page-level restrictions    | spaces ENG · SEC · FIN |
| Jira         | project roles + issue-level security          | projects MIG · PAY · SEC · HELP |
| Slack        | channel membership (public / private)         | threads as resources |
| Google Drive | file / folder sharing (view · comment · edit) | shared drives |

`upload.py` is a fifth, runtime-ingestion connector. It is kept on the backend
(`/upload`, usable from the API docs page) to show connector extensibility but
is not surfaced in the UI. Connectors without their own permission rules get
the generic fail-closed ACL check (deny-list → user grant → role grant →
deny).

### `backend/auth/`

- `identity.py` — 7 seed personas.
- `roles.py` — 7 roles and their permissions (`read`, `cite`, `export`,
  `audit_query`, `manage_permissions`).

### `backend/policy/`

- `policy_engine.py` — fail-closed `decide(user, resource, action) → Decision`.
- `permission_mapping.py` — source-specific rules + sensitivity clearance +
  action permissions.
- `freshness_checker.py` — indexed vs live ACL version comparison (INV3).
- `admin.py` — revoke/grant; every change bumps the resource's ACL version.
- `inspector.py` — read-only "who can access what" by user, role, or resource,
  computed by the real PolicyEngine.

### `backend/retrieval/`

- `indexer.py` — snapshots connector resources (content + indexed ACL version);
  intended for search rather than authorization; missing live-ACL fallback is an exception noted below.
- `candidate_search.py` — TF-IDF + character n-gram search over every source.
  Explicit report labels (`Q` followed by digits) require an exact token in the
  document title/content; unrelated periods are excluded (ADR-0008).
  Deliberately over-fetches. Naming a platform in the question ("…raised in
  Slack?") **boosts** that source's resources; it never drops the others
  ([ADR-0006](decisions/0006-source-mentions-boost-not-filter.md)).
- `permission_filter.py` — re-fetches each candidate's live ACL and runs the
  PolicyEngine; drops denied resources (INV1/INV2).
- `context_assembler.py` — bounded, citation-marked context of allowed content.
- `pipeline.py` — search → filter → assemble.

### `backend/agents/`

- `orchestrator.py` — the query pipeline above, plus `export()` (EXPORT
  re-check per resource) and `preview()` (raw-source read: READ re-check,
  audited, denied ≡ not found).
- `adp_client.py` — Tencent Cloud ADP Chat API adapter (SSE, UTF-8, fresh
  conversation per call, OS trust store for TLS-intercepted networks).
- `llm_client.py` — `LLMClient` protocol + deterministic extractive stub used
  offline and as the runtime fallback (ADR-0005).
- `answer_agent.py` — grounded answer from the assembled context; strips
  citations not backed by it (INV6); canonical no-access message (INV7).
- `grounding_checker.py` — lexical sentence/context checks (INV8), not semantic
  verification. The orchestrator retains the original citation-validated answer
  if every sentence is rejected; otherwise rejected sentences are removed. Capitalized phrases and hyphenated terms are checked word by
  word; month names match ISO dates; "9 AM" matches "9AM". The count of
  removed sentences is returned to the UI.
- `query_scanner.py` — flags prompt-injection patterns in the audit trail
  (never trusted to block; the permission filter is the guard).

### `backend/audit/`

- `event_schema.py` — canonical `AuditEvent`; deterministic JSON payload.
- `hash_chain.py` — `event_hash = SHA256(prev_hash + canonical_json(event))`;
  appends each event as one JSON line (never rewriting earlier lines);
  `verify_file()` re-hashes the file and compares its length and head with
  the in-memory chain, so edits, corrupt lines and deleted tail events are
  all caught. Every audit query runs this check.
- `audit_query.py` — filters by user, resource (substring or id set), query,
  decision, action, time window.
- `nl_query.py` — deterministic plain-English audit search. Resolves users,
  time windows, decisions, platforms, Confluence spaces, Jira projects, Slack
  channels, and resource titles against the live catalog, and reports any
  words it could not map instead of silently ignoring them.

### `backend/api/` (FastAPI)

| Route | Gate | Purpose |
|---|---|---|
| `GET /health`, `GET /users` | — | liveness + LLM mode; persona switcher |
| `POST /query` | — | answer, citations, decisions (deny details only for auditors), `grounding_removed` |
| `GET /resource/{id}` | `export` | raw source for the preview panel; READ re-checked, audited, denied ≡ not found |
| `POST /export` | `export` | download; EXPORT re-checked per resource and audited |
| `GET /audit`, `GET /audit/search` | `audit_query` | structured and plain-English audit queries |
| `GET /audit/verify`, `GET /audit/verify-file` | `audit_query` | in-memory chain check; re-hash the on-disk log |
| `POST /admin/revoke`, `POST /admin/grant` | `manage_permissions` | ACL change with version transition |
| `GET /admin/permissions/*` | `manage_permissions` | permissions inspector |
| `POST/GET /upload` | `manage_permissions` | runtime ingestion (not in the UI) |

`state.py` holds one shared orchestrator so revocations persist across
requests within one process. ACL changes, uploads and the chain are process-local;
startup truncates the audit file. Exactly one worker/instance is required.
Routes are thin adapters over the layers below.

### `frontend/`

`index.html` + `app.js`, no build step locally. The API origin comes from
`config.js` (local default `http://localhost:8000`); for Vercel,
`scripts/build.cjs` copies the UI to `dist/` and writes `config.js` from
`TIANQUAN_API_BASE`. Tailwind's browser build is vendored and pinned in
`frontend/vendor/` so the demo never depends on a CDN. Panels
render by permission: the source preview only for `export`, the audit explorer
for `audit_query`, revoke/grant and the inspector for `manage_permissions`.
In the audit explorer each query's logged answer shows which document every
`[n]` cites, and each allowed document is marked "cited" or "not cited".
A **clean mode** toggle removes the CRT effects for readability; the UI is
keyboard-operable (persona listbox, tabs, citation cards) with visible focus.

## 4. Data models

### Resource

```python
{
    "source": "confluence" | "jira" | "slack" | "gdrive" | "upload",
    "resource_id": str,
    "title": str,
    "content": str,
    "updated_at": datetime,
    "url": str,                       # link back to the source system
    "sensitivity_level": "public" | "internal" | "restricted" | "confidential",
    "acl": {
        "acl_version": int,           # bumped on every permission change
        "allowed_users": [str],
        "allowed_roles": [str],
        "denied_users": [str],
        "source_permissions": {...},  # native model, e.g. {"space": "ENG", "page_restriction": None}
    },
}
```

### Decision

```python
{
    "user_id": str,
    "resource_id": str | None,        # None for the answer event
    "action": "read" | "cite" | "export",
    "result": "allow" | "deny",
    "reason": str,
    "acl_version": int,
    "policy_version": int,
    "timestamp": datetime,
}
```

### AuditEvent (hashed payload)

```python
{
    "event_id": str,
    "timestamp": datetime,
    "user_id": str,
    "query_id": str,                  # groups one query's events
    "resource_id": str | None,
    "action": str,
    "decision": "allow" | "deny" | "change",
    "reason": str,
    "question": str,                  # the user's question, on every event of a query
    "detail": str,                    # answer text on the answer event; "source_preview" on previews
    "citations": [{"marker": "[1]", "resource_id": str}],  # answer event: what each [n] cites
    "acl_version": int,
    "policy_version": int,
    "previous_hash": str,
    "event_hash": str,                # SHA256(previous_hash + canonical payload)
}
```

## 5. Request lifecycle

```
1. UI sends POST /query {user_id, question} with X-User-Id.
2. Orchestrator:
   a. Scan the question for injection patterns (flag only).
   b. Candidate search across all sources (over-fetch; named platforms boosted).
   c. For each candidate: fetch the LIVE ACL, PolicyEngine.decide(user, r, read).
   d. Assemble allowed content into a cited context window.
   e. Audit every decision (allow and deny) with the question before generation.
   f. ADP drafts the answer (fresh conversation); stub fallback on failure.
   g. Strip out-of-context citations (INV6); apply lexical grounding/fallback (INV8).
   h. Audit the answer event (question + answer text + marker -> resource map).
3. Return {answer, citations, decisions*, grounding_removed, audit_chain_head}.
   * deny details only for callers with audit_query.
```

## 6. ACL versioning & freshness

Each resource carries an ACL version, incremented on every permission change.
The indexer records the version at index time; supported connectors return
current ACLs to the filter, so a revoke takes effect on the next query with
no reindex. Content remains the indexed snapshot until explicit reindex
(initialization and upload trigger indexing); each citation carries the
source `updated_at`. These labels do not guarantee a live content fetch.

## 7. No-metadata-leak behavior

For a non-auditor query with no accessible matches, the asker does not see the denied resource's title, ID, or a "you don't
have permission" message (which would confirm existence). The user sees the
canonical *"I could not find accessible information matching your request."*
The same holds for the source preview: a denied and a nonexistent resource get
the identical 404. Denials are recorded in the audit log for compliance.

## 8. Formal model boundary

The TLA+ specification (`formal/`) models a single query's lifecycle — search →
decide (with audit) → retrieve → answer — with revocation able to fire at any point
up to retrieval. TLC checks INV1–INV4, INV6, and INV7 over every reachable
state of the configured two-user/two-resource model; the naive variant (trusting the decide-time snapshot) leaks under a
revoke-after-decide race. The spec is an abstract model; the implementation is
tested against corresponding properties (294 tests verified on 2026-10-12).
There is no verified refinement from TLA+ to Python. INV5 is deferred; INV8 is
a Python grounding heuristic, outside the six modeled invariants.

## 9. Technology choices

| Decision     | Choice | Rationale |
|--------------|--------|-----------|
| Backend      | Python / FastAPI | Fast to prototype; good fit for LLM work |
| Frontend     | Static HTML/JS (Miora-generated design) | No build step; vendored Tailwind for offline demos |
| LLM          | Tencent Cloud ADP | Hackathon track requirement; swappable via `LLMClient` |
| Formal model | TLA+ / TLC | Best fit for temporal safety properties such as revocation races |
| Audit log    | Hash-chained JSONL on disk | Simple, transparent, demonstrable tamper-evidence |
| Dev tool     | CodeBuddy | Required proof of usage |
| Hosting      | Vercel (static UI) + Render (one backend instance) | Simple, free-tier demo hosting; no shared-storage migration needed ([ADR-0009](decisions/0009-cloud-demo-with-process-local-state.md)) |

## 10. Prototype limits and deployment boundary

The demo is deployed ([deployment plan](deployment-plan.md), [ADR-0009](decisions/0009-cloud-demo-with-process-local-state.md)): the static UI on Vercel at https://tianquan.vercel.app and one backend instance on Render's free tier at `https://tianquan-api.onrender.com`, with no shared-storage migration. CORS allows only the configured frontend origins (`TIANQUAN_ALLOWED_ORIGINS`) — a browser restriction, not authentication. The free tier sleeps after ~15 idle minutes; a restart, redeploy or wake resets demo state and truncates the audit file. `/health` reports configured mode rather than successful live generation.

The current implementation has no production authentication, synchronization for concurrent audit appends, externally anchored ledger or durable startup recovery. ACL retrieval and context assembly are separate operations; the model does not establish all concurrent Python schedules are safe. A missing connector ACL returns the indexed resource, which can still be permitted by the policy engine. All-rejected grounding restores the original answer. These gaps and their follow-ups are tracked in [current state](current-state.md#known-boundaries-and-follow-ups).

The direct published ADP chat bypasses this application pipeline. Use the full deployed frontend to demonstrate Tianquan's permission and audit features. Keep synthetic data and backend-only credentials.
