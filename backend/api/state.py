"""Shared application state for the API layer.

Holds the singletons the routes operate on: the connectors, the identity
store, the orchestrator (which owns the retrieval pipeline, audit chain, and
permission admin), and an audit query engine over the same chain.

A single shared orchestrator is intentional: revocations made via the admin
routes must be visible to subsequent /query calls within the same process
(Demo 3). Everything is in-memory (ADR-0003 spirit) — fine for the demo.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()  # reads .env in project root if present (gitignored)

from backend.agents.orchestrator import Orchestrator
from backend.audit.audit_query import AuditQueryEngine
from backend.auth.identity import IdentityStore
from backend.connectors.confluence import ConfluenceConnector
from backend.connectors.gdrive import GDriveConnector
from backend.connectors.jira import JiraConnector
from backend.connectors.slack import SlackConnector
from backend.connectors.upload import UploadConnector


def _build_llm():
    """Return an ADP LLM client if an AppKey is set, else the stub.

    ADP_APP_KEY can be set via environment variable. When absent, the
    deterministic stub is used so the system runs fully offline (ADR-0005).
    """
    if os.environ.get("ADP_APP_KEY"):
        try:
            from backend.agents.adp_client import ADPClient
            return ADPClient()
        except Exception:
            pass  # fall through to stub
    from backend.agents.llm_client import StubLLMClient
    return StubLLMClient()


@dataclass
class AppState:
    """Container for the API's shared singletons."""

    identity: IdentityStore
    orchestrator: Orchestrator
    audit_query: AuditQueryEngine
    upload_connector: UploadConnector

    @classmethod
    def create(cls) -> "AppState":
        """Build a fresh application state with seed connectors and users."""
        upload = UploadConnector()
        connectors = [
            ConfluenceConnector(),
            JiraConnector(),
            SlackConnector(),
            GDriveConnector(),
            upload,
        ]
        orchestrator = Orchestrator(connectors, llm=_build_llm())
        return cls(
            identity=IdentityStore(),
            orchestrator=orchestrator,
            audit_query=AuditQueryEngine(orchestrator.audit),
            upload_connector=upload,
        )