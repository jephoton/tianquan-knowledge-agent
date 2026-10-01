"""FastAPI application factory.

Assembles the query, audit, and admin routers over a shared AppState.
Run for the demo with:

    uvicorn backend.api.app:app --reload

Or build a fresh app in tests with `create_app()`.
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import admin_routes, audit_routes, query_routes
from backend.api.state import AppState


def create_app() -> FastAPI:
    """Create a FastAPI app with a fresh, self-contained AppState."""
    app = FastAPI(
        title="Tianquan 天权 API",
        version="0.1.0",
        description="Permission-aware enterprise knowledge agent.",
    )

    # Permissive CORS for the local Miora/React dev frontend (M8).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.tianquan = AppState.create()

    @app.get("/health", tags=["meta"])
    def health() -> dict:
        return {
            "status": "ok",
            "llm": "adp" if os.environ.get("ADP_APP_KEY") else "stub",
        }

    @app.get("/users", tags=["meta"])
    def users() -> list[dict]:
        """List seed users for the demo persona switcher."""
        store = app.state.tianquan.identity
        return [
            {"user_id": u.user_id, "name": u.name, "roles": u.roles,
             "department": u.department, "is_contractor": u.is_contractor}
            for u in store.all_users().values()
        ]

    app.include_router(query_routes.router)
    app.include_router(audit_routes.router)
    app.include_router(admin_routes.router)
    return app


# Module-level app for `uvicorn backend.api.app:app`.
app = create_app()
