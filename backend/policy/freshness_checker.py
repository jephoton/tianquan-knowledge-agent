"""ACL freshness checker.

Validates that the ACL version known to the caller (e.g., the indexer
or retrieval pipeline) matches the live ACL version on the resource.

This supports INV3 (RevokedAccessNotReusable): after a permission
revocation, the ACL version increments, and any cached or stale
permission snapshot is detected as stale, forcing a re-evaluation
through the policy engine.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.models import Resource


@dataclass
class FreshnessResult:
    """Result of an ACL freshness check."""

    is_fresh: bool
    known_version: int
    current_version: int
    reason: str


def check_freshness(resource: Resource, known_acl_version: int) -> FreshnessResult:
    """Check if a known ACL version matches the resource's current version.

    Args:
        resource: The live resource with its current ACL.
        known_acl_version: The ACL version the caller cached at ingestion time.

    Returns:
        FreshnessResult indicating whether the version is current.
    """
    current = resource.acl.acl_version

    if known_acl_version == current:
        return FreshnessResult(
            is_fresh=True,
            known_version=known_acl_version,
            current_version=current,
            reason="acl_version_current",
        )

    if known_acl_version < current:
        return FreshnessResult(
            is_fresh=False,
            known_version=known_acl_version,
            current_version=current,
            reason=f"acl_version_stale:cached={known_acl_version},live={current}",
        )

    # known > current should never happen with monotonic versioning,
    # but we treat it as stale (fail-closed) rather than allowing it.
    return FreshnessResult(
        is_fresh=False,
        known_version=known_acl_version,
        current_version=current,
        reason=f"acl_version_anomaly:cached={known_acl_version},live={current}",
    )


def assert_fresh(resource: Resource, known_acl_version: int) -> bool:
    """Return True only if the ACL version is current.

    Convenience function for callers that only need the boolean.
    Fail-closed: any mismatch returns False.
    """
    return check_freshness(resource, known_acl_version).is_fresh