"""Role definitions and role-to-permission mapping for Tianquan."""

from __future__ import annotations

# Role hierarchy (higher index = more privileged within a department)
ROLES = {
    "contractor": {
        "description": "External contractor with limited, explicit access only",
        "default_permissions": ["read"],
    },
    "engineer": {
        "description": "Backend/frontend engineer with internal access",
        "default_permissions": ["read", "cite"],
    },
    "senior_engineer": {
        "description": "Senior engineer with broader internal access",
        "default_permissions": ["read", "cite", "export"],
    },
    "finance_analyst": {
        "description": "Finance team member with access to financial documents",
        "default_permissions": ["read", "cite", "export"],
    },
    "security_team": {
        "description": "Security team member with access to restricted security content + audit trail",
        "default_permissions": ["read", "cite", "export", "audit_query"],
    },
    "compliance_officer": {
        "description": "Compliance officer with audit trail query access",
        "default_permissions": ["read", "cite", "export", "audit_query"],
    },
    "admin": {
        "description": "System administrator with permission management access",
        "default_permissions": ["read", "cite", "export", "audit_query", "manage_permissions"],
    },
}


def role_exists(role: str) -> bool:
    """Check if a role name is valid."""
    return role in ROLES


def get_role_permissions(role: str) -> list[str]:
    """Get the default permissions for a role."""
    return ROLES.get(role, {}).get("default_permissions", [])


# Permissions that grant access to the admin / audit surfaces.
ADMIN_PERMISSIONS = frozenset({"manage_permissions", "audit_query"})


def role_set_permissions(roles: list[str]) -> set[str]:
    """Union of all permissions across the given roles."""
    perms: set[str] = set()
    for role in roles:
        perms.update(get_role_permissions(role))
    return perms


def has_permission(roles: list[str], permission: str) -> bool:
    """True if any of the user's roles grants `permission`."""
    return permission in role_set_permissions(roles)


def can_audit(roles: list[str]) -> bool:
    """May view the audit trail / policy decisions (audit_query)."""
    return has_permission(roles, "audit_query")


def can_manage(roles: list[str]) -> bool:
    """May revoke/grant permissions and upload documents (manage_permissions)."""
    return has_permission(roles, "manage_permissions")


def can_export(roles: list[str]) -> bool:
    """May export answers / cited resources (export)."""
    return has_permission(roles, "export")


def is_privileged(roles: list[str]) -> bool:
    """True if the user can reach the admin tab at all (any admin permission).

    Granular gating uses `can_audit` / `can_manage`; this is the coarse
    "shows something in Admin" check used by the frontend tab gate.
    """
    return bool(ADMIN_PERMISSIONS & role_set_permissions(roles))