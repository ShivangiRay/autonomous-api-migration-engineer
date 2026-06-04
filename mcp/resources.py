"""
MCP Resources: migration_templates

Exposes 4 standard boilerplate templates as MCP resources so LLMs can read
consistent, canonical migration boilerplate when writing or reviewing code.

Resource URIs:
  migration://templates/proto_header     — .proto file header with package/option placeholders
  migration://templates/error_mapping    — gRPC ↔ HTTP status code mapping table
  migration://templates/interceptors     — logging, auth, and retry interceptor boilerplate
  migration://templates/grpc_client      — gRPC client stub template
"""
from __future__ import annotations

from mcp.templates.error_mapping import ERROR_MAPPING_DESCRIPTION, ERROR_MAPPING_TEMPLATE
from mcp.templates.grpc_client import GRPC_CLIENT_DESCRIPTION, GRPC_CLIENT_TEMPLATE
from mcp.templates.interceptors import INTERCEPTORS_DESCRIPTION, INTERCEPTORS_TEMPLATE
from mcp.templates.proto_header import PROTO_HEADER_DESCRIPTION, PROTO_HEADER_TEMPLATE

# Registry mapping URI → (content, description, mime_type)
RESOURCE_REGISTRY: dict[str, dict[str, str]] = {
    "migration://templates/proto_header": {
        "name": "proto_header",
        "uri": "migration://templates/proto_header",
        "description": PROTO_HEADER_DESCRIPTION,
        "content": PROTO_HEADER_TEMPLATE,
        "mime_type": "text/plain",
    },
    "migration://templates/error_mapping": {
        "name": "error_mapping",
        "uri": "migration://templates/error_mapping",
        "description": ERROR_MAPPING_DESCRIPTION,
        "content": ERROR_MAPPING_TEMPLATE,
        "mime_type": "text/markdown",
    },
    "migration://templates/interceptors": {
        "name": "interceptors",
        "uri": "migration://templates/interceptors",
        "description": INTERCEPTORS_DESCRIPTION,
        "content": INTERCEPTORS_TEMPLATE,
        "mime_type": "text/x-python",
    },
    "migration://templates/grpc_client": {
        "name": "grpc_client",
        "uri": "migration://templates/grpc_client",
        "description": GRPC_CLIENT_DESCRIPTION,
        "content": GRPC_CLIENT_TEMPLATE,
        "mime_type": "text/x-python",
    },
}


def list_resources() -> list[dict[str, str]]:
    """Return all available template resources (for MCP ListResources)."""
    return [
        {
            "uri": v["uri"],
            "name": v["name"],
            "description": v["description"],
            "mimeType": v["mime_type"],
        }
        for v in RESOURCE_REGISTRY.values()
    ]


def read_resource(uri: str) -> dict[str, str]:
    """Return the content of a resource by URI (for MCP ReadResource)."""
    entry = RESOURCE_REGISTRY.get(uri)
    if entry is None:
        available = list(RESOURCE_REGISTRY.keys())
        raise ValueError(f"Unknown resource URI '{uri}'. Available: {available}")
    return {
        "uri": entry["uri"],
        "mimeType": entry["mime_type"],
        "text": entry["content"],
    }
