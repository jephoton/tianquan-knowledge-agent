"""User identities and identity store for VeriBrain.

Seed users are designed to cover all demo scenarios:
- Alice: engineer with access to migration project + payment incident channel
- Bob: external contractor with limited access
- Charlie: security team member with restricted content access
- Diana: compliance officer for audit inquiry demos
- jdoe: generic user for audit trail queries
"""

from __future__ import annotations

from backend.models import User


def seed_users() -> dict[str, User]:
    """Return the initial set of seed users keyed by user_id."""
    return {
        "alice": User(
            user_id="alice",
            name="Alice Chen",
            email="alice.chen@companya.com",
            roles=["engineer"],
            department="Engineering",
            is_contractor=False,
        ),
        "bob": User(
            user_id="bob",
            name="Bob Contractor",
            email="bob@externalvendor.com",
            roles=["contractor"],
            department="External",
            is_contractor=True,
        ),
        "charlie": User(
            user_id="charlie",
            name="Charlie Ng",
            email="charlie.ng@companya.com",
            roles=["security_team"],
            department="Security",
            is_contractor=False,
        ),
        "diana": User(
            user_id="diana",
            name="Diana Tan",
            email="diana.tan@companya.com",
            roles=["compliance_officer"],
            department="Compliance",
            is_contractor=False,
        ),
        "jdoe": User(
            user_id="jdoe",
            name="John Doe",
            email="john.doe@companya.com",
            roles=["senior_engineer"],
            department="Engineering",
            is_contractor=False,
        ),
        "erin": User(
            user_id="erin",
            name="Erin Wong",
            email="erin.wong@companya.com",
            roles=["finance_analyst"],
            department="Finance",
            is_contractor=False,
        ),
        "frank": User(
            user_id="frank",
            name="Frank Lim",
            email="frank.lim@companya.com",
            roles=["admin"],
            department="IT",
            is_contractor=False,
        ),
    }


class IdentityStore:
    """In-memory identity store."""

    def __init__(self) -> None:
        self._users = seed_users()

    def get_user(self, user_id: str) -> User | None:
        return self._users.get(user_id)

    def add_user(self, user: User) -> None:
        self._users[user.user_id] = user

    def all_users(self) -> dict[str, User]:
        return dict(self._users)