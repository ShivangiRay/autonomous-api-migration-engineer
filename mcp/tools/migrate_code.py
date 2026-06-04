"""
MCP Tool: migrate_code

Takes a REST source file (OpenAPI spec) and an endpoint ID, then runs the full
REST-to-gRPC migration pipeline end-to-end — fully agentic, no human checkpoint:

  1. ScannerAgent     — parse the OpenAPI spec
  2. ArchitecturePlannerAgent — classify and plan the migration
  3. propose_grpc()   — generate a GrpcMigrationProposal
  4. ApprovalAgent    — auto-approve the proposal (LLM-driven mode)
  5. ImplementationAgent — scaffold the gRPC service impl, stubs, and tests

Returns the paths of every generated file plus the proto content and service
implementation code so the LLM can read and further refine them inline.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from agents.approval.agent import ApprovalAgent
from agents.implementation.agent import ImplementationAgent
from agents.planner.agent import ArchitecturePlannerAgent
from agents.scanner.agent import ScannerAgent
from libs.common.models import MigrationTarget
from libs.common.proposals import propose_grpc


def migrate_code(
    endpoint_id: str,
    openapi_path: str | None = None,
    openapi_content: str | None = None,
    output_dir: str = "build/mcp_migration",
    memory_path: str | None = None,
) -> dict[str, Any]:
    """
    Run the full REST-to-gRPC migration pipeline for a single endpoint (auto-approve).

    The LLM drives every stage with no human checkpoint:
    - Scans the OpenAPI spec
    - Plans the migration and validates the endpoint is a gRPC candidate
    - Generates a GrpcMigrationProposal with a .proto definition
    - Auto-approves the proposal
    - Scaffolds the gRPC service implementation, server init, and mapping test

    Args:
        endpoint_id: The endpoint to migrate (e.g. "POST /users").
        openapi_path: Filesystem path to the OpenAPI YAML/JSON spec.
        openapi_content: Raw YAML or JSON string (alternative to openapi_path).
        output_dir: Root directory for generated files (default: build/mcp_migration).
        memory_path: Optional path to the migration memory JSONL store for RAG context.

    Returns:
        A dict with:
          - endpoint_id: the migrated endpoint
          - migration_target: the planner's recommendation (should be "migrate_grpc")
          - proposal_path: path to the approved GrpcMigrationProposal JSON
          - proposal_id: the proposal ID
          - proto_content: the generated .proto text
          - generated_files: list of all scaffolded file paths
          - file_contents: dict mapping each generated file path → its text content
          - memory_cases_used: number of similar RAG memory cases retrieved
          - rationale: planner rationale for the gRPC recommendation
          - confidence: planner confidence score
    """
    spec_path = _resolve_spec(openapi_path, openapi_content)

    # ── 1. Scan ──────────────────────────────────────────────────────────────
    inventory = ScannerAgent().scan(spec_path)

    # ── 2. Plan ──────────────────────────────────────────────────────────────
    plan = ArchitecturePlannerAgent().plan(inventory)
    rec = next((r for r in plan.recommendations if r.endpoint_id == endpoint_id), None)
    if rec is None:
        available = [r.endpoint_id for r in plan.recommendations]
        raise ValueError(f"endpoint_id '{endpoint_id}' not found. Available: {available}")

    if rec.target != MigrationTarget.GRPC:
        return {
            "endpoint_id": endpoint_id,
            "migration_target": rec.target.value,
            "skipped": True,
            "reason": (
                f"Endpoint is recommended as '{rec.target.value}', not 'migrate_grpc'. "
                "Use migrate_code only on gRPC-recommended endpoints. "
                f"Rationale: {rec.rationale}"
            ),
        }

    # ── 3. Generate proposal ─────────────────────────────────────────────────
    proposal_dir = str(Path(output_dir) / "proposals")
    proposal_path = propose_grpc(
        openapi_path=spec_path,
        endpoint_id=endpoint_id,
        output_dir=proposal_dir,
        memory_path=memory_path,
    )

    # Read proposal to extract memory context info
    raw_proposal = json.loads(Path(proposal_path).read_text())
    memory_cases_used = len(raw_proposal.get("basis", {}).get("retrieved_memory_cases", []))

    # ── 4. Auto-approve ───────────────────────────────────────────────────────
    approval_agent = ApprovalAgent()
    approved_proposal = approval_agent.approve(str(proposal_path))

    # ── 5. Scaffold implementation ───────────────────────────────────────────
    impl_dir = str(Path(output_dir) / "implementation")
    generated_paths = ImplementationAgent().implement(str(proposal_path), impl_dir)

    # Read all generated file contents for inline LLM inspection
    file_contents: dict[str, str] = {}
    for p in generated_paths:
        try:
            file_contents[str(p)] = Path(p).read_text()
        except Exception:
            file_contents[str(p)] = "<unreadable>"

    return {
        "endpoint_id": endpoint_id,
        "migration_target": rec.target.value,
        "skipped": False,
        "proposal_path": str(proposal_path),
        "proposal_id": approved_proposal.id,
        "proto_content": approved_proposal.proposed_proto,
        "generated_files": [str(p) for p in generated_paths],
        "file_contents": file_contents,
        "memory_cases_used": memory_cases_used,
        "rationale": rec.rationale,
        "confidence": rec.confidence,
        "phase": rec.phase,
        "output_dir": output_dir,
    }


def _resolve_spec(openapi_path: str | None, openapi_content: str | None) -> str:
    if openapi_content is not None:
        suffix = ".yaml" if openapi_content.strip().startswith(("openapi:", "swagger:")) else ".json"
        with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False) as tmp:
            tmp.write(openapi_content)
            return tmp.name
    if openapi_path is not None:
        return openapi_path
    raise ValueError("Provide either openapi_path or openapi_content.")
