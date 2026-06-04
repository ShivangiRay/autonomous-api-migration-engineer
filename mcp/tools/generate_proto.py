"""
MCP Tool: generate_proto

Generates proto3 file syntax from an analyzed REST schema.
Accepts either a full OpenAPI spec path/content (generates a complete service .proto)
or a single endpoint_id within a spec (generates a focused single-rpc .proto).
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from agents.planner.agent import ArchitecturePlannerAgent
from agents.scanner.agent import ScannerAgent
from libs.contracts.protobuf import render_endpoint_proto, render_proto
from mcp.templates.proto_header import PROTO_HEADER_TEMPLATE


def generate_proto(
    openapi_path: str | None = None,
    openapi_content: str | None = None,
    endpoint_id: str | None = None,
    output_path: str | None = None,
    include_header_template: bool = True,
) -> dict[str, Any]:
    """
    Generate proto3 file syntax from an OpenAPI/Swagger spec.

    Modes:
    - Full service: omit endpoint_id → generates a single .proto covering all
      gRPC-recommended endpoints in the service.
    - Single endpoint: provide endpoint_id (e.g. "POST /users") → generates a
      focused .proto with one rpc method and its request/response messages.

    Args:
        openapi_path: Filesystem path to the OpenAPI YAML/JSON spec.
        openapi_content: Raw YAML or JSON string of the spec (alternative to path).
        endpoint_id: Filter to a single endpoint (e.g. "GET /users/{id}").
        output_path: If provided, write the generated .proto to this file path.
        include_header_template: If True, prepend the canonical proto header
            template with package/option placeholders.

    Returns:
        A dict with keys:
          - proto_content: the generated proto3 text
          - mode: "full_service" | "single_endpoint"
          - service_name: detected service name from the spec
          - rpc_count: number of rpc methods generated
          - output_path: where the file was written (or null)
          - header_template: the proto header boilerplate (if include_header_template)
    """
    spec_path = _resolve_spec(openapi_path, openapi_content)

    inventory = ScannerAgent().scan(spec_path)
    plan = ArchitecturePlannerAgent().plan(inventory)

    if endpoint_id:
        # Single-endpoint mode
        endpoint = next((ep for ep in inventory.endpoints if ep.id == endpoint_id), None)
        if endpoint is None:
            available = [ep.id for ep in inventory.endpoints]
            raise ValueError(f"endpoint_id '{endpoint_id}' not found. Available: {available}")
        proto_content = render_endpoint_proto(inventory.service_name, endpoint)
        mode = "single_endpoint"
        rpc_count = 1
    else:
        # Full service mode
        proto_content = render_proto(inventory, plan)
        from libs.common.models import MigrationTarget
        rpc_count = sum(1 for r in plan.recommendations if r.target == MigrationTarget.GRPC)
        mode = "full_service"

    written_path: str | None = None
    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(proto_content)
        written_path = str(out.resolve())

    result: dict[str, Any] = {
        "proto_content": proto_content,
        "mode": mode,
        "service_name": inventory.service_name,
        "rpc_count": rpc_count,
        "output_path": written_path,
    }
    if include_header_template:
        result["header_template"] = PROTO_HEADER_TEMPLATE
        result["header_note"] = (
            "The header_template above is the canonical .proto file header with package "
            "and language-option placeholders. Replace <org>, <service>, <version>, and "
            "<Service> before use."
        )
    return result


def _resolve_spec(openapi_path: str | None, openapi_content: str | None) -> str:
    """Return a filesystem path to the spec, writing a temp file if needed."""
    if openapi_content is not None:
        suffix = ".yaml" if openapi_content.strip().startswith(("openapi:", "swagger:")) else ".json"
        with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False) as tmp:
            tmp.write(openapi_content)
            return tmp.name
    if openapi_path is not None:
        return openapi_path
    raise ValueError("Provide either openapi_path or openapi_content.")
