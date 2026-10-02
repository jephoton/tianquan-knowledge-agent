"""Upload routes — POST /upload, POST /upload/reindex.

Backs Demo 7 (real-time data ingestion). An admin uploads a document
(title + text content), it becomes a first-class Resource in the
upload connector, and a reindex makes it searchable immediately.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/upload", tags=["upload"])


class UploadDocument(BaseModel):
    resource_id: str
    title: str
    content: str
    allowed_roles: list[str] | None = None
    denied_users: list[str] | None = None


@router.post("")
def upload_document(request: Request, doc: UploadDocument) -> dict:
    """Upload a document to the upload connector and reindex."""
    state = request.app.state.tianquan
    state.upload_connector.add_document(
        resource_id=doc.resource_id,
        title=doc.title,
        content=doc.content,
        allowed_roles=doc.allowed_roles,
        denied_users=doc.denied_users,
    )
    count = state.orchestrator.reindex()
    return {
        "resource_id": doc.resource_id,
        "title": doc.title,
        "indexed_resources": count,
        "message": f"Document '{doc.title}' uploaded and indexed ({count} total resources).",
    }


@router.get("")
def list_uploads(request: Request) -> dict:
    """List all uploaded documents."""
    state = request.app.state.tianquan
    resources = state.upload_connector.list_resources()
    return {
        "count": len(resources),
        "documents": [
            {
                "resource_id": r.resource_id,
                "title": r.title,
                "updated": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in resources
        ],
    }
