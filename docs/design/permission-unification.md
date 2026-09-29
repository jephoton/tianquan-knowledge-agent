# Design — Permission Model Unification

> **Last updated:** 2026-09-29

## Problem

VeriBrain integrates four source systems (Confluence, Jira, Slack, Google
Drive), each with a fundamentally different native permission model:

| Source | Native model |
|--------|-------------|
| Confluence | Spaces (public/internal/restricted) + page-level restrictions (named/editors) |
| Jira | Projects with project-roles + issue-level security schemes |
| Slack | Channels (public/private/DM) with membership |
| Google Drive | File/folder sharing (view/comment/edit) + shared drives |

We need a single pipeline (search → filter → assemble → answer) that works
uniformly across all four, while still honouring each source's native rules.

## Solution: two-layer unification

### Layer 1 — Common `Resource` + `ACL` shape

Every resource, regardless of source, is translated into the same Python
dataclass at connector construction time:

```python
Resource {
    source: Source              # CONFLUENCE | JIRA | SLACK | GDRIVE
    resource_id: str
    title: str
    content: str
    updated_at: datetime
    sensitivity_level: SensitivityLevel  # PUBLIC | INTERNAL | RESTRICTED | CONFIDENTIAL
    acl: ACL {
        acl_version: int
        allowed_users: list[str]
        allowed_roles: list[str]
        denied_users: list[str]
        source_permissions: dict   # native escape hatch
    }
}
```

The `allowed_users` / `allowed_roles` / `denied_users` lists create a
**common permission surface** — the policy engine can check them uniformly
without knowing which source the resource came from.

The `source_permissions` dict is the **escape hatch** that preserves each
platform's native semantics. Each connector populates it differently:

| Source | `source_permissions` shape |
|--------|------------------------------|
| Confluence | `{"space": "ENG", "page_restriction": "named"}` |
| Jira | `{"project": "MIG", "issue_security": "security"}` |
| Slack | `{"channel": "#sec-incidents", "channel_type": "private"}` |
| GDrive | `{"drive": "Finance", "share_type": "view"}` |

So the common lists say *who* can access, while `source_permissions` carries
*where* and *how* the access is scoped in native terms.

### Layer 2 — Source-specific checkers

When the policy engine authorizes access,
`permission_mapping.check_source_specific(user, resource)` dispatches to a
source-specific function that reads `source_permissions` and applies native
rules:

- **Confluence** — If `page_restriction == "named"`, space-level access is
  ignored. Only explicit `allowed_users`/`allowed_roles` entries apply.
  Otherwise standard ACL check with space-level logging.
- **Jira** — If `issue_security == "security"`, only `security_team` or
  explicit named users can see the issue, even if the project grants access to
  all engineers.
- **Slack** — `channel_type == "public"` means all workspace members see it
  (unless explicitly denied). Private channels and DMs require explicit ACL
  membership.
- **GDrive** — Standard ACL check with drive-aware logging.

## The unification contract

1. Each connector **translates** its native objects into the common
   `Resource`/`ACL` shape (including populating `source_permissions`).
2. The policy engine checks `allowed_users`/`allowed_roles`/`denied_users`
   **uniformly** (deny-list → source-specific → sensitivity → action).
3. `source_permissions` is only consulted **inside** the source-specific
   checker — the rest of the system never reads it.

## Extending to a new source

To add a 5th source (e.g. Notion), you must touch **4 files** — but none of
them are in the retrieval pipeline, audit, answer, or API layers:

| Step | File | Work |
|------|------|------|
| 1. Add `NOTION` to the `Source` enum | `backend/models.py` | 1 line |
| 2. Write a connector class extending `BaseConnector` | `backend/connectors/notion.py` | ~100 lines: translate native objects to `Resource`/`ACL` with `source_permissions` |
| 3. Add `_check_notion()` to the permission mapping | `backend/policy/permission_mapping.py` | ~30 lines: native permission rules |
| 4. Register the connector | `backend/api/state.py` | 1 line: `NotionConnector()` in the list |

**What does NOT change:**

- `indexer.py` — iterates `connector.list_resources()` generically
- `candidate_search.py` — scores `Resource.title` + `Resource.content` generically
- `permission_filter.py` — calls `PolicyEngine.decide()` generically
- `context_assembler.py` — assembles `Resource.content` generically
- `answer_agent.py` — generates from assembled context generically
- `orchestrator.py` — sequences the pipeline generically
- `audit/` — logs `Decision` objects generically
- `api/routes` — pass through to orchestrator generically
- Frontend — reads API responses generically

You cannot avoid writing the connector itself — every source has different
data shapes and permission models that must be translated. But the design
ensures the translation is the **only** new code.