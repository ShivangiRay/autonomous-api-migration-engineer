from __future__ import annotations

import re
from pathlib import Path

from agents.planner.agent import ArchitecturePlannerAgent
from agents.scanner.agent import ScannerAgent
from libs.common.models import GrpcMigrationProposal, MigrationTarget
from libs.contracts.protobuf import render_endpoint_proto


def propose_grpc(openapi_path: str | Path, endpoint_id: str, output_dir: str | Path) -> Path:
    inventory = ScannerAgent().scan(openapi_path)
    endpoint = next((item for item in inventory.endpoints if item.id == endpoint_id), None)
    if endpoint is None:
        raise ValueError(f"Endpoint not found: {endpoint_id}")

    plan = ArchitecturePlannerAgent().plan(inventory)
    recommendation = next(item for item in plan.recommendations if item.endpoint_id == endpoint_id)
    if recommendation.target != MigrationTarget.GRPC:
        raise ValueError(f"{endpoint_id} is recommended as {recommendation.target.value}, not gRPC.")

    proposal = GrpcMigrationProposal(
        id=_proposal_id(endpoint_id),
        endpoint_id=endpoint_id,
        basis={
            "trained_on": "No project-specific training. Deterministic rules over supplied OpenAPI/source evidence.",
            "source_openapi": str(openapi_path),
            "endpoint_evidence": endpoint.evidence,
            "planner_rationale": recommendation.rationale,
            "confidence": recommendation.confidence,
            "request_schema": endpoint.request_schema,
            "response_schema": endpoint.response_schema,
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


def _proposal_id(endpoint_id: str) -> str:
    return "proposal-" + re.sub(r"[^a-zA-Z0-9]+", "-", endpoint_id).strip("-").lower()

