"""Pydantic request/response models for the API layer.

These are the wire contract the frontend (M8) codes against. They mirror the
internal dataclasses but are decoupled from them, so internal refactors do not
silently change the API.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# -- /query ------------------------------------------------------------

class QueryRequest(BaseModel):
    user_id: str = Field(..., description="Seed user id, e.g. 'alice'.")
    question: str = Field(..., min_length=1)
    k: int = Field(10, ge=1, le=50, description="Candidate over-fetch size.")


class CitationModel(BaseModel):
    marker: str
    resource_id: str
    source: str
    title: str
    updated_at: str | None = None


class DecisionModel(BaseModel):
    user_id: str
    resource_id: str | None
    action: str
    result: str
    reason: str
    acl_version: int
    policy_version: int


class QueryResponseModel(BaseModel):
    query_id: str
    answer: str
    no_access: bool
    citations: list[CitationModel]
    decisions: list[DecisionModel]
    allow_count: int
    deny_count: int
    viewer_privileged: bool = False
    viewer_can_export: bool = False
    audit_chain_head: str


# -- /audit ------------------------------------------------------------

class AuditEventModel(BaseModel):
    event_id: str
    timestamp: str
    user_id: str
    query_id: str
    resource_id: str | None
    action: str
    decision: str
    reason: str
    acl_version: int
    policy_version: int
    previous_hash: str
    event_hash: str


class AuditQueryResponseModel(BaseModel):
    count: int
    allow_count: int
    deny_count: int
    chain_valid: bool
    chain_status: str
    events: list[AuditEventModel]


# -- /admin ------------------------------------------------------------

class RevokeGrantRequest(BaseModel):
    resource_id: str
    subject: str = Field(..., description="A user_id or a role name.")
    subject_kind: str = Field("user", pattern="^(user|role)$")


class ACLChangeModel(BaseModel):
    resource_id: str
    previous_version: int
    new_version: int
    version_transition: str
    change: str
    subject: str
    subject_kind: str
