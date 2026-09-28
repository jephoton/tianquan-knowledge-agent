"""Shared application state for the API layer.

Holds the singletons the routes operate on: the connectors, the identity
store, the orchestrator (which owns the retrieval pipeline, audit chain, and
permission admin), and an audit query engine over the same chain.

A single shared orchestrator is intentional: revocations made via the admin
routes must be visible to subsequent /query calls within the same process
(Demo 3). Everything is in-memory (ADR-0003 spirit) — fine for the demo.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.agents.orchestrator import Orchestrator
from backend.audit.audit_query import AuditQueryEngine
from backend.auth.identity import IdentityStore
from backend.connectors.confluence import ConfluenceConnector
from backend.connectors.gdrive import GDriveConnector
from backend.connectors.jira import JiraConnector
from backend.connectors.slack import SlackConnector


@dataclass
class AppState:
    """Container for the API's shared singletons."""

    identity: IdentityStore
    orchestrator: Orchestrator
    audit_query: AuditQueryEngine

    @classmethod
    def create(cls) -> "AppState":
        """Build a fresh application state with seed connectors and users."""
        connectors = [
            ConfluenceConnector(),
            JiraConnector(),
            SlackConnector(),
            GDriveConnector(),
        ]
        orchestrator = Orchestrator(connectors)
        return cls(
            identity=IdentityStore(),
            orchestrator=orchestrator,
            audit_query=AuditQueryEngine(orchestrator.audit),
        )
