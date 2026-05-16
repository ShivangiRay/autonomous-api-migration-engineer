from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class MigrationTarget(str, Enum):
    REST = "keep_rest"
    GRPC = "migrate_grpc"
    EVENT = "convert_event"
    SPLIT = "split_context"
    DEPRECATE = "deprecate_or_merge"


class Endpoint(BaseModel):
    id: str
    method: str
    path: str
    operation_id: str
    domain: str
    summary: str = ""
    request_schema: dict = Field(default_factory=dict)
    response_schema: dict = Field(default_factory=dict)
    auth: str = "unknown"
    pagination: bool = False
    idempotency: bool = False
    evidence: list[str] = Field(default_factory=list)


class ServiceInventory(BaseModel):
    service_name: str
    endpoints: list[Endpoint]
    detected_patterns: list[str] = Field(default_factory=list)
    source_evidence: list[str] = Field(default_factory=list)


class Recommendation(BaseModel):
    endpoint_id: str
    target: MigrationTarget
    phase: int
    rationale: str
    confidence: float
    impacted_dependencies: list[str] = Field(default_factory=list)


class MigrationPlan(BaseModel):
    service_name: str
    recommendations: list[Recommendation]
    readiness_score: int
    rollout_phases: dict[str, list[str]]


class GeneratedArtifact(BaseModel):
    artifact_type: str
    path: str
    provenance: dict
    approval_status: str = "pending_human_approval"


class CompatibilityFinding(BaseModel):
    endpoint_id: str
    severity: str
    message: str
    evidence: list[str] = Field(default_factory=list)


class CompatibilityReport(BaseModel):
    service_name: str
    score: int
    findings: list[CompatibilityFinding]


class ProposalComment(BaseModel):
    author: str = "developer"
    body: str
    resolved: bool = False


class GrpcMigrationProposal(BaseModel):
    id: str
    endpoint_id: str
    status: str = "needs_review"
    basis: dict
    proposed_proto: str
    comments: list[ProposalComment] = Field(default_factory=list)
    generated_files: list[str] = Field(default_factory=list)
