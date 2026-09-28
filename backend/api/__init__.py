"""FastAPI REST layer for VeriBrain.

- app:          application factory + module-level `app` for uvicorn.
- state:        shared singletons (connectors, identity, orchestrator).
- schemas:      Pydantic request/response models (the wire contract).
- query_routes / audit_routes / admin_routes: the endpoints.
"""

from backend.api.app import create_app, app

__all__ = ["create_app", "app"]
