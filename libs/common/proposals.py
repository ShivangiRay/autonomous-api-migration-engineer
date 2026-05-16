from __future__ import annotations

import re
from pathlib import Path

from agents.planner.agent import ArchitecturePlannerAgent
from agents.scanner.agent import ScannerAgent
from libs.common.memory import MigrationMemoryStore
from libs.common.models import EventMigrationProposal, GrpcMigrationProposal, MigrationTarget
from libs.contracts.events import render_asyncapi
from libs.contracts.protobuf import render_endpoint_proto
from libs.contracts.transport import recommend_event_transport


def propose_grpc(
    openapi_path: str | Path,
    endpoint_id: str,
    output_dir: str | Path,
    memory_path: str | Path | None = None,
) -> Path:
    inventory = ScannerAgent().scan(openapi_path)
    endpoint = next((item for item in inventory.endpoints if item.id == endpoint_id), None)
    if endpoint is None:
        raise ValueError(f"Endpoint not found: {endpoint_id}")

    plan = ArchitecturePlannerAgent().plan(inventory)
    recommendation = next(item for item in plan.recommendations if item.endpoint_id == endpoint_id)
    if recommendation.target != MigrationTarget.GRPC:
        raise ValueError(f"{endpoint_id} is recommended as {recommendation.target.value}, not gRPC.")

    memory = MigrationMemoryStore(memory_path) if memory_path else MigrationMemoryStore()
    similar_cases = memory.similar(endpoint, recommendation.target.value)
    proposal = GrpcMigrationProposal(
        id=_proposal_id(endpoint_id),
        endpoint_id=endpoint_id,
        basis={
            "trained_on": "No project-specific training. RAG retrieves local approved/generated cases; rules use supplied OpenAPI/source evidence.",
            "source_openapi": str(openapi_path),
            "endpoint_evidence": endpoint.evidence,
            "planner_rationale": recommendation.rationale,
            "confidence": recommendation.confidence,
            "request_schema": endpoint.request_schema,
            "response_schema": endpoint.response_schema,
            "retrieved_memory_cases": [case.model_dump() for case in similar_cases],
            "rag_adjustments": _memory_adjustments(similar_cases),
        },
        proposed_proto=render_endpoint_proto(inventory.service_name, endpoint),
    )
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{proposal.id}.json"
    if path.exists():
        raise FileExistsError(f"Proposal already exists: {path}")
    path.write_text(proposal.model_dump_json(indent=2))
    return path


def propose_event(
    openapi_path: str | Path,
    endpoint_id: str,
    output_dir: str | Path,
    memory_path: str | Path | None = None,
) -> Path:
    inventory = ScannerAgent().scan(openapi_path)
    endpoint = next((item for item in inventory.endpoints if item.id == endpoint_id), None)
    if endpoint is None:
        raise ValueError(f"Endpoint not found: {endpoint_id}")

    plan = ArchitecturePlannerAgent().plan(inventory)
    recommendation = next(item for item in plan.recommendations if item.endpoint_id == endpoint_id)
    if recommendation.target != MigrationTarget.EVENT:
        raise ValueError(f"{endpoint_id} is recommended as {recommendation.target.value}, not event-driven.")

    memory = MigrationMemoryStore(memory_path) if memory_path else MigrationMemoryStore()
    similar_cases = memory.similar(endpoint, recommendation.target.value)
    proposal = EventMigrationProposal(
        id=_proposal_id(endpoint_id) + "-event",
        endpoint_id=endpoint_id,
        basis={
            "trained_on": "No project-specific training. RAG retrieves local approved/generated cases; rules use supplied OpenAPI/source evidence.",
            "source_openapi": str(openapi_path),
            "endpoint_evidence": endpoint.evidence,
            "planner_rationale": recommendation.rationale,
            "confidence": recommendation.confidence,
            "operation_id": endpoint.operation_id,
            "retrieved_memory_cases": [case.model_dump() for case in similar_cases],
            "rag_adjustments": _memory_adjustments(similar_cases),
        },
        transport_recommendation=recommend_event_transport(endpoint, len(similar_cases)),
        proposed_asyncapi=render_asyncapi(inventory, plan),
        similar_memory_cases=similar_cases,
    )
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{proposal.id}.json"
    if path.exists():
        raise FileExistsError(f"Proposal already exists: {path}")
    path.write_text(proposal.model_dump_json(indent=2))
    return path


def _proposal_id(endpoint_id: str) -> str:
    return "proposal-" + re.sub(r"[^a-zA-Z0-9]+", "-", endpoint_id).strip("-").lower()


def _memory_adjustments(cases: list) -> list[str]:
    adjustments: list[str] = []
    for case in cases:
        adjustments.extend(case.learned_adjustments)
    return sorted(set(adjustments))
