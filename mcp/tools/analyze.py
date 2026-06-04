"""
MCP Tool: analyze_rest_endpoint

Takes a REST controller file or an OpenAPI/Swagger spec and outputs a detailed
analysis of how each endpoint should map to gRPC — including HTTP verb → rpc
method mapping, payload shapes to message blocks, and per-endpoint recommendations.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from agents.planner.agent import ArchitecturePlannerAgent
from agents.scanner.agent import ScannerAgent
from libs.common.models import Endpoint, MigrationTarget


# HTTP verb → gRPC pattern advice
_VERB_TO_GRPC: dict[str, dict[str, str]] = {
    "GET": {
        "pattern": "Unary RPC",
        "rpc_style": "rpc Get<Resource>(<Resource>Request) returns (<Resource>Response);",
        "notes": "Use server-streaming if the response is a large collection.",
    },
    "POST": {
        "pattern": "Unary RPC",
        "rpc_style": "rpc Create<Resource>(Create<Resource>Request) returns (Create<Resource>Response);",
        "notes": "Consider client-streaming if the payload is chunked (e.g. file upload).",
    },
    "PUT": {
        "pattern": "Unary RPC",
        "rpc_style": "rpc Replace<Resource>(Replace<Resource>Request) returns (<Resource>Response);",
        "notes": "Full replacement — include all fields in the request message.",
    },
    "PATCH": {
        "pattern": "Unary RPC with FieldMask",
        "rpc_style": "rpc Update<Resource>(Update<Resource>Request) returns (<Resource>Response);",
        "notes": "Use google.protobuf.FieldMask in the request to represent partial updates.",
    },
    "DELETE": {
        "pattern": "Unary RPC",
        "rpc_style": "rpc Delete<Resource>(Delete<Resource>Request) returns (google.protobuf.Empty);",
        "notes": "Return Empty for idempotent deletes; return the deleted resource for audit trails.",
    },
}

_TARGET_NOTES: dict[MigrationTarget, str] = {
    MigrationTarget.GRPC: "✅ Recommended for gRPC migration.",
    MigrationTarget.EVENT: "📨 Better suited as an async event (Kafka/RabbitMQ). Consider AsyncAPI contract.",
    MigrationTarget.REST: "🔁 Keep as REST — collection reads or externally-facing endpoints.",
    MigrationTarget.SPLIT: "✂️  Crosses bounded contexts — split the domain before migrating the protocol.",
    MigrationTarget.DEPRECATE: "🗑️  Overlaps newer capabilities — deprecate or merge first.",
}


def _json_type_to_proto(json_type: str) -> str:
    return {
        "integer": "int32",
        "number": "double",
        "boolean": "bool",
        "array": "repeated string",
        "object": "bytes",  # use bytes + JSON encoding or a nested message
    }.get(json_type, "string")


def _schema_to_message_fields(schema: dict[str, Any]) -> list[dict[str, str]]:
    """Convert a JSON Schema object to a list of proto field descriptors."""
    fields: list[dict[str, str]] = []
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    for idx, (name, prop) in enumerate(properties.items(), start=1):
        json_type = prop.get("type", "string")
        proto_type = _json_type_to_proto(json_type)
        fields.append(
            {
                "field_number": str(idx),
                "proto_type": proto_type,
                "name": name,
                "required": str(name in required),
                "description": prop.get("description", ""),
            }
        )
    if not fields:
        # No properties — use a generic request_id field
        fields.append({"field_number": "1", "proto_type": "string", "name": "request_id", "required": "false", "description": "Opaque request identifier."})
    return fields


def _analyze_endpoint(endpoint: Endpoint, recommendation: Any) -> dict[str, Any]:
    verb_info = _VERB_TO_GRPC.get(endpoint.method, _VERB_TO_GRPC["GET"])
    return {
        "endpoint_id": endpoint.id,
        "http_method": endpoint.method,
        "path": endpoint.path,
        "operation_id": endpoint.operation_id,
        "summary": endpoint.summary,
        "grpc_mapping": {
            "recommended_target": recommendation.target.value,
            "recommendation_note": _TARGET_NOTES[recommendation.target],
            "confidence": recommendation.confidence,
            "phase": recommendation.phase,
            "rationale": recommendation.rationale,
        },
        "rpc_pattern": {
            "pattern": verb_info["pattern"],
            "rpc_signature": verb_info["rpc_style"]
            .replace("<Resource>", _pascal(endpoint.operation_id))
            .replace("Create<Resource>", "Create" + _pascal(endpoint.operation_id))
            .replace("Replace<Resource>", "Replace" + _pascal(endpoint.operation_id))
            .replace("Update<Resource>", "Update" + _pascal(endpoint.operation_id))
            .replace("Delete<Resource>", "Delete" + _pascal(endpoint.operation_id)),
            "notes": verb_info["notes"],
        },
        "request_message": {
            "name": f"{_pascal(endpoint.operation_id)}Request",
            "fields": _schema_to_message_fields(endpoint.request_schema),
        },
        "response_message": {
            "name": f"{_pascal(endpoint.operation_id)}Response",
            "fields": _schema_to_message_fields(endpoint.response_schema),
        },
        "metadata": {
            "auth": endpoint.auth,
            "pagination": endpoint.pagination,
            "idempotency": endpoint.idempotency,
            "domain": endpoint.domain,
            "evidence": endpoint.evidence,
        },
    }


def _pascal(value: str) -> str:
    import re
    words: list[str] = []
    for chunk in re.split(r"[^a-zA-Z0-9]+", value):
        if not chunk:
            continue
        words.extend(re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)|[0-9]+", chunk))
    return "".join(part[:1].upper() + part[1:] for part in words)


def analyze_rest_endpoint(
    openapi_path: str | None = None,
    openapi_content: str | None = None,
    endpoint_id: str | None = None,
) -> dict[str, Any]:
    """
    Analyze a REST OpenAPI spec and produce a gRPC mapping analysis.

    Provide either a file path (openapi_path) or the raw YAML/JSON content
    (openapi_content). Optionally filter to a single endpoint by endpoint_id
    (e.g. "GET /users/{id}").

    Returns a structured analysis with per-endpoint gRPC mapping, RPC pattern
    advice, proto message field shapes, and migration recommendations.
    """
    if openapi_content is not None:
        # Write content to a temp file so the parser can handle it
        suffix = ".yaml" if openapi_content.strip().startswith(("openapi:", "swagger:")) else ".json"
        with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False) as tmp:
            tmp.write(openapi_content)
            spec_path = tmp.name
    elif openapi_path is not None:
        spec_path = openapi_path
    else:
        raise ValueError("Provide either openapi_path or openapi_content.")

    inventory = ScannerAgent().scan(spec_path)
    plan = ArchitecturePlannerAgent().plan(inventory)

    rec_by_id = {r.endpoint_id: r for r in plan.recommendations}

    endpoints_to_analyze = inventory.endpoints
    if endpoint_id:
        endpoints_to_analyze = [ep for ep in inventory.endpoints if ep.id == endpoint_id]
        if not endpoints_to_analyze:
            available = [ep.id for ep in inventory.endpoints]
            raise ValueError(f"endpoint_id '{endpoint_id}' not found. Available: {available}")

    analyses = [_analyze_endpoint(ep, rec_by_id[ep.id]) for ep in endpoints_to_analyze]

    grpc_count = sum(1 for r in plan.recommendations if r.target == MigrationTarget.GRPC)
    event_count = sum(1 for r in plan.recommendations if r.target == MigrationTarget.EVENT)
    rest_count = sum(1 for r in plan.recommendations if r.target == MigrationTarget.REST)

    return {
        "service_name": inventory.service_name,
        "total_endpoints": len(inventory.endpoints),
        "readiness_score": plan.readiness_score,
        "summary": {
            "grpc_candidates": grpc_count,
            "event_candidates": event_count,
            "keep_rest": rest_count,
            "other": len(inventory.endpoints) - grpc_count - event_count - rest_count,
        },
        "detected_patterns": inventory.detected_patterns,
        "rollout_phases": plan.rollout_phases,
        "endpoint_analyses": analyses,
    }
