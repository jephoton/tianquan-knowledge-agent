# Architecture — VeriBrain

> **Last updated:** 2026-09-29

## 1. System overview

```
┌─────────────────────────────────────────────────────┐
│                     Frontend (Miora)                   │
│  Query Console  ·  Policy Inspector  ·  Audit Explorer │
└────────────────────────┬────────────────────────────┘
                         │ REST / JSON
┌────────────────────────▼────────────────────────────┐
│                   Backend (FastAPI)                    │
│ ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│ │   API   │→ │Orchestr. │→ │  Answer  │→ │  Audit  │ │
│ │ Routes  │  │  Agent   │  │  Agent   │  │  Logger │ │
│ └─────────┘  └────┬─────┘  └────▲─────┘  └─────────┘ │
│                   │              │                     │
│         ┌─────────▼──────────────┴─────────┐          │
│         │     Permission-Aware Retrieval    │          │
│         │  ┌──────────┐  ┌───────────────┐  │          │
│         │  │ Candidate │→ │ Policy Filter │  │          │
│         │  │  Search   │  │ (pre-LLM)     │  │          │
│         │  └────▲─────┘  └───────┬───────┘  │          │
│         └───────┼────────────────┼──────────┘          │
│                 │                │                      │
│   ┌─────────────▼────┐   ┌───────▼────────┐            │
│   │  Policy Engine   │   │   Context      │            │
│   │  (auth decision) │   │   Assembler    │            │
│   └────────┬─────────┘   └────────────────┘            │
│            │                                            │
│   ┌────────▼──────────────────────────────────┐       │
│   │          Connectors (mock)                 │       │
│   │  Confluence · Jira · Slack · Google Drive  │       │
│   └────────────────────────────────────────────┘       │
└────────────────────────────────────────────────────────┘
```

## 2. Trust boundaries

```
User (authenticated)
  │
  ▼ trust boundary 1: identity verified
API Layer
  │
  ▼ trust boundary 2: policy engine is authoritative
Policy Engine ←── ACL store (versioned)
  │
  ▼ trust boundary 3: only authorized content passes
Retrieval → Context Assembler
  │
  ▼ trust boundary 4: LLM sees only filtered context
LLM Answer Agent
  │
  ▼ trust boundary 5: answer + citations logged
Audit Log (hash-chained, tamper-evident)
```

The critical invariant across all trust boundaries:

> **The LLM never receives content the user is not authorized to see. Filtering happens before the LLM, not after.**

## 3. Module map

### `backend/connectors/`

Mock source-system connectors. Each connector exposes:

- `list_resources()` — returns resource metadata with ACL info.
- `get_resource(id)` — returns full content + current ACL.
- `get_acl(id)` — returns current ACL version and permission entries.
- `check_membership(user, resource)` — source-native permission check.

Each connector preserves its source-specific permission model:

| Source         | Permission model                          |
|----------------|-------------------------------------------|
| Confluence     | space-level + page-level restrictions     |
| Jira           | project-role + issue-level security       |
| Slack          | channel membership (public/private/DM)    |
| Google Drive   | file-folder-user sharing (view/comment/edit) |

### `backend/auth/`

- `identity.py` — user identity store with 7 seed users.
- `roles.py` — role definitions and role-to-permission mapping.

### `backend/policy/`

The authorization core.

- `policy_engine.py` — `decide(user, resource, action) → Decision(allow, reason, acl_version)`.
- `permission_mapping.py` — maps source-specific permission models to a common model.
- `freshness_checker.py` — validates ACL version at query time vs. ingestion time.
- `admin.py` — live permission admin (revoke/grant) with ACL version bumping.

### `backend/retrieval/`

- `indexer.py` — indexes resources from all connectors with ACL snapshot.
- `candidate_search.py` — retrieves candidate resource IDs for a query.
- `permission_filter.py` — filters candidates through the policy engine before LLM.
- `context_assembler.py` — assembles approved content into a coherent LLM context window.

### `backend/agents/`

- `orchestrator.py` — routes user query through the pipeline.
- `answer_agent.py` — generates grounded answer with citations from filtered context.
- `grounding_checker.py` — post-LLM hallucination detection; strips ungrounded sentences (INV8).
- `query_scanner.py` — prompt-injection detection; flags suspicious queries in the audit trail.

### `backend/audit/`

- `event_schema.py` — canonical audit event structure.
- `hash_chain.py` — `event_hash = SHA256(prev_hash + canonical_json(event))`.
- `audit_query.py` — query API for compliance officers.

### `backend/api/` (FastAPI — implemented)

- `app.py` — application factory + module-level `app` (`uvicorn backend.api.app:app`).
- `state.py` — shared singletons; a single `Orchestrator` so revocations persist across requests.
- `schemas.py` — Pydantic request/response models (the frontend wire contract).
- `query_routes.py` — POST `/query`.
- `audit_routes.py` — GET `/audit`, GET `/audit/verify`.
- `admin_routes.py` — POST `/admin/revoke`, POST `/admin/grant`.
- Meta: GET `/health`, GET `/users` (persona switcher).

The API is a thin adapter: authorization, retrieval, and audit all live in the
layers below. Routes translate between the Pydantic wire models and the
internal orchestrator/audit/admin services.

## 4. Data models

### Resource

```python
{
    "source": "confluence" | "jira" | "slack" | "gdrive",
    "resource_id": str,
    "title": str,
    "content": str,
    "updated_at": datetime,
    "acl_version": int,
    "allowed_users": [str],
    "allowed_roles": [str],
    "sensitivity_level": "public" | "internal" | "restricted" | "confidential",
    "source_permissions": {  # source-specific
        # e.g. confluence: {"space": "ENG", "page_restriction": "editors"}
    }
}
```

### Decision

```python
{
    "user_id": str,
    "resource_id": str,
    "action": "read" | "cite" | "export",
    "decision": "allow" | "deny",
    "reason": str,
    "acl_version": int,
    "policy_version": int,
    "timestamp": datetime,
}
```

### AuditEvent

```python
{
    "event_id": str,
    "timestamp": datetime,
    "user_id": str,
    "query_id": str,
    "resource_id": str | null,
    "action": str,
    "decision": "allow" | "deny",
    "reason": str,
    "acl_version": int,
    "policy_version": int,
    "previous_hash": str,
    "event_hash": str,
}
```

## 5. Request lifecycle

```
1. User authenticates → session token with identity + roles.
2. User submits query → POST /query {question}.
3. Orchestrator:
   a. Resolve identity + roles from session.
   b. Candidate search → list of (source, resource_id) candidates.
   c. For each candidate:
      - Fetch current ACL from connector.
      - Policy engine: decide(user, resource, "read").
      - Record Decision + AuditEvent.
   d. Assemble allowed content into context window.
   e. Answer agent: generate answer + citations from context.
   f. Verify every citation corresponds to an allowed resource.
   g. Log answer AuditEvent.
4. Return: {answer, citations, decisions, audit_chain_head}.
```

## 6. ACL versioning & freshness

Each resource carries an `acl_version` integer, incremented on every permission change.

- At indexing time, the indexer records `indexed_acl_version`.
- At query time, the policy engine fetches `current_acl_version`.
- If `indexed_acl_version != current_acl_version`, the policy engine re-checks against the current ACL.
- This ensures revoked permissions are never served from stale indexes.

## 7. No-metadata-leak behavior

On denial, the user-facing answer never includes:

- The denied resource's title.
- The denied resource's ID or path.
- The reason "you don't have permission" (which confirms existence).

Instead:

- User sees: "I could not find accessible information matching your request."
- Audit log records: the denied resource, the reason, the ACL version.

## 8. Formal model boundary

The TLA+ specification models:

- The state machine of: query → candidate → policy decision → retrieval → answer → audit.
- ACL version transitions (including revocation).
- The 7 invariants listed in [plan.md](plan.md#4-formal-verification-story).

The specification is an abstract model. The implementation should be tested against the same properties via property tests.

## 9. Technology choices

| Decision       | Choice          | Rationale                                          |
|----------------|-----------------|----------------------------------------------------|
| Backend        | Python / FastAPI | Fast to prototype, async support, good for LLM work |
| Frontend       | Static HTML/JS (Miora-generated UI) | No build step; Miora produced the dashboard, wired to the API via vanilla JS. |
| Formal model   | TLA+ / TLC      | Best for temporal safety properties, revocation     |
| Audit log      | Hash-chained JSON | Simple, transparent, demonstrable tamper-evidence |
| LLM            | Tencent Cloud LLM | Track requirement to use Tencent Cloud AI products |
| UI design      | Miora            | Tencent Cloud AI creative studio for production-grade UI |
| Dev tool       | CodeBuddy        | Required proof of usage for submission             |