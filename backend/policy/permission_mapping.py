"""Source-specific permission model mapping.

Each connector preserves its native permission semantics in
ACL.source_permissions. This module translates those into a
common model that the policy engine can reason about uniformly.

The common model has three dimensions:
- user_access: Does the user have explicit or role-based access?
- action_allowed: Is the requested action permitted by the user's roles?
- sensitivity_ok: Is the user cleared for the resource's sensitivity level?

Source-specific rules are applied first, then the common rules
act as a secondary gate. This preserves native semantics while
giving the policy engine a uniform decision surface.
"""

from __future__ import annotations

from backend.models import Action, ACL, Resource, SensitivityLevel, Source, User


# Sensitivity clearance matrix: which roles can access which sensitivity levels.
# Higher sensitivity requires more privileged roles.
SENSITIVITY_CLEARANCE: dict[SensitivityLevel, set[str]] = {
    SensitivityLevel.PUBLIC: {
        "contractor", "engineer", "senior_engineer",
        "finance_analyst", "security_team", "compliance_officer", "admin",
    },
    SensitivityLevel.INTERNAL: {
        "engineer", "senior_engineer",
        "finance_analyst", "security_team", "compliance_officer", "admin",
    },
    SensitivityLevel.RESTRICTED: {
        "senior_engineer",
        "finance_analyst", "security_team", "compliance_officer", "admin",
    },
    SensitivityLevel.CONFIDENTIAL: {
        "security_team", "compliance_officer", "admin",
    },
}


def check_source_specific(user: User, resource: Resource) -> tuple[bool, str]:
    """Apply source-specific permission rules.

    Returns (allowed, reason). This is the first gate: it checks
    the native permission model before common rules are applied.
    A deny here is definitive; an allow here still needs to pass
    the common rules.
    """
    sp = resource.acl.source_permissions

    if resource.source == Source.CONFLUENCE:
        return _check_confluence(user, resource, sp)
    if resource.source == Source.JIRA:
        return _check_jira(user, resource, sp)
    if resource.source == Source.SLACK:
        return _check_slack(user, resource, sp)
    if resource.source == Source.GDRIVE:
        return _check_gdrive(user, resource, sp)
    return True, "unknown_source_default_allow"


def check_sensitivity_clearance(user: User, resource: Resource) -> tuple[bool, str]:
    """Check if the user's roles clear the resource's sensitivity level."""
    cleared = SENSITIVITY_CLEARANCE.get(resource.sensitivity_level, set())
    if any(role in cleared for role in user.roles):
        return True, "sensitivity_cleared"
    return False, f"sensitivity_{resource.sensitivity_level.value}_not_cleared"


def check_action_permission(user: User, action: Action) -> tuple[bool, str]:
    """Check if the user's roles permit the requested action."""
    from backend.auth.roles import get_role_permissions

    for role in user.roles:
        perms = get_role_permissions(role)
        if action.value in perms:
            return True, f"action_{action.value}_allowed_by_role:{role}"
    return False, f"action_{action.value}_not_permitted"


# -- Source-specific checks ---------------------------------------------

def _check_confluence(
    user: User, resource: Resource, sp: dict,
) -> tuple[bool, str]:
    """Confluence: space-level + page-level restrictions.

    Page restriction 'named' means only explicitly named users/roles
    can see the page, regardless of space visibility.
    """
    space = sp.get("space", "")
    page_restriction = sp.get("page_restriction")

    # If page has 'named' restriction, only explicit ACL entries apply.
    if page_restriction == "named":
        if user.user_id in resource.acl.allowed_users:
            return True, f"confluence_named_page_explicit_user:{space}"
        if any(r in resource.acl.allowed_roles for r in user.roles):
            return True, f"confluence_named_page_role:{space}"
        return False, f"confluence_named_page_no_access:{space}"

    # Default: standard ACL check (space-level visibility).
    if user.user_id in resource.acl.denied_users:
        return False, f"confluence_space_denied:{space}"
    if user.user_id in resource.acl.allowed_users:
        return True, f"confluence_space_explicit_user:{space}"
    if any(r in resource.acl.allowed_roles for r in user.roles):
        return True, f"confluence_space_role:{space}"
    return False, f"confluence_space_no_access:{space}"


def _check_jira(
    user: User, resource: Resource, sp: dict,
) -> tuple[bool, str]:
    """Jira: project-role + issue-level security.

    Issue security 'security' restricts visibility to security_team
    role or explicitly named users, overriding project-level access.
    """
    project = sp.get("project", "")
    issue_security = sp.get("issue_security")

    if issue_security == "security":
        if user.user_id in resource.acl.allowed_users:
            return True, f"jira_security_issue_explicit_user:{project}"
        if "security_team" in user.roles or "admin" in user.roles:
            return True, f"jira_security_issue_role:{project}"
        return False, f"jira_security_issue_no_access:{project}"

    # Standard project-level ACL check.
    if user.user_id in resource.acl.denied_users:
        return False, f"jira_project_denied:{project}"
    if user.user_id in resource.acl.allowed_users:
        return True, f"jira_project_explicit_user:{project}"
    if any(r in resource.acl.allowed_roles for r in user.roles):
        return True, f"jira_project_role:{project}"
    return False, f"jira_project_no_access:{project}"


def _check_slack(
    user: User, resource: Resource, sp: dict,
) -> tuple[bool, str]:
    """Slack: channel membership (public, private, DM).

    Public channels: visible to all workspace members (all roles).
    Private channels: visible only to explicit members/roles.
    DMs: visible only to participants.
    """
    channel = sp.get("channel", "")
    channel_type = sp.get("channel_type", "public")

    if channel_type == "public":
        if user.user_id in resource.acl.denied_users:
            return False, f"slack_public_denied:{channel}"
        return True, f"slack_public_member:{channel}"

    # private or DM: explicit ACL only.
    if user.user_id in resource.acl.allowed_users:
        return True, f"slack_{channel_type}_explicit_user:{channel}"
    if any(r in resource.acl.allowed_roles for r in user.roles):
        return True, f"slack_{channel_type}_role:{channel}"
    return False, f"slack_{channel_type}_no_access:{channel}"


def _check_gdrive(
    user: User, resource: Resource, sp: dict,
) -> tuple[bool, str]:
    """Google Drive: file-folder-user sharing (view, comment, edit).

    Shared drives: visible to drive members (role-based).
    Personal shares: visible only to explicitly named users.
    """
    drive = sp.get("drive", "")
    share_type = sp.get("share_type", "view")

    if user.user_id in resource.acl.denied_users:
        return False, f"gdrive_denied:{drive}"
    if user.user_id in resource.acl.allowed_users:
        return True, f"gdrive_explicit_user:{drive}"
    if any(r in resource.acl.allowed_roles for r in user.roles):
        return True, f"gdrive_role:{drive}"
    return False, f"gdrive_no_access:{drive}"