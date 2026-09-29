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

To add a 5th source (e.g. Notion):

1. Write a new connector that emits `Resource` objects with
   `source_permissions = {"workspace": "...", "share_level": "..."}`.
2. Add a `_check_notion` function in `permission_mapping.py`.
3. Add `NOTION` to the `Source` enum in `models.py`.

The retrieval pipeline, audit trail, answer agent, and frontend do not change.