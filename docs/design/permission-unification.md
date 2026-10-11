# Design — Permission Model Unification

> **Last updated:** 2026-10-11

<!-- Generated reconciliation of source scope and extension guidance. -->

## Problem

Tianquan models four source systems through mock connectors (Confluence, Jira, Slack, Google
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
    source: Source              # CONFLUENCE | JIRA | SLACK | GDRIVE | UPLOAD
    resource_id: str
    title: str
    content: str
    updated_at: datetime
    url: str
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
- **Jira** — If `issue_security == "security"`, only `security_team`, `admin` or
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
3. Source-specific authorization is centralized in the checker. Catalog and
   audit-search code also reads source metadata to resolve source/container names;
   that metadata does not independently authorize access.

## Extending to a new source

Typical changes are a `Source` enum member in `backend/models.py`, a `BaseConnector` implementation, source-specific permission rules in `backend/policy/permission_mapping.py` and registration in `backend/api/state.py`. Add connector/policy tests and inspect API/frontend labels and seed assumptions; the exact file count depends on the source. The generic retrieval, assembly and audit interfaces can usually remain unchanged.

A connector must translate source objects into `Resource`/`ACL`, preserving source semantics. Unknown-source rules use deny-list → explicit user grant → role grant → deny. That is distinct from a missing ACL: the filter currently falls back to the indexed resource when `get_acl()` returns `None`, which can be allowed. Address unavailable/deleted ACLs explicitly before adding real source connections. See [pipeline mapping](pipeline-and-invariants.md) and [known limits](../current-state.md#known-boundaries-and-follow-ups).
