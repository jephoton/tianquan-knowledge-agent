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
        "description": "Security team member with access to restricted security content",
        "default_permissions": ["read", "cite", "export"],
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


def is_privileged(roles: list[str]) -> bool:
    """True if any of the user's roles can access admin/audit surfaces.

    Privileged = holds `manage_permissions` (admin) or `audit_query`
    (compliance_officer). This is the single source of truth for whether a
    persona may revoke/grant, query the audit trail, or see deny details.
    """
    for role in roles:
        if ADMIN_PERMISSIONS & set(get_role_permissions(role)):
            return True
    return False