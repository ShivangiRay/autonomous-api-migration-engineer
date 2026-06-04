"""
Autonomous API Migration Engineer — MCP Server

Exposes 4 Tools and 4 Resources over the Model Context Protocol so any
MCP-compatible LLM host (Claude Desktop, Cursor, Gemini CLI, etc.) can drive
REST-to-gRPC migrations programmatically.

Transport modes
───────────────
  stdio (default)   Works with Claude Desktop, Cursor, Gemini CLI — no port needed.
  HTTP / SSE        Run `migration-engineer-mcp --http` to serve on a local port
                    (default 8000). Useful for web-based LLM integrations.

Quick start
───────────
  # stdio (for Claude Desktop / Cursor / Gemini CLI)
  migration-engineer-mcp

  # HTTP + SSE
  migration-engineer-mcp --http --port 8000

Tools
─────
  analyze_rest_endpoint   Scan an OpenAPI spec and produce a gRPC mapping analysis
  generate_proto          Generate .proto3 syntax for a full service or single endpoint
  migrate_code            Run the full agentic migration pipeline (auto-approve)
  generate_grpc_client    Generate Python gRPC client stubs to replace HTTP clients

Resources
─────────
  migration://templates/proto_header    Standard .proto file header boilerplate
  migration://templates/error_mapping   gRPC ↔ HTTP status code mapping table
  migration://templates/interceptors    Logging / auth / retry interceptor boilerplate
  migration://templates/grpc_client     Python gRPC client stub template
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Any

from mcp.resources import list_resources, read_resource
from mcp.tools.analyze import analyze_rest_endpoint
from mcp.tools.generate_grpc_client import generate_grpc_client
from mcp.tools.generate_proto import generate_proto
from mcp.tools.migrate_code import migrate_code

logger = logging.getLogger(__name__)

# ── Try to import the official MCP SDK ───────────────────────────────────────
try:
    import mcp.server.stdio  # noqa: F401 — presence check
    from mcp.server import Server
    from mcp.server.models import InitializationOptions
    import mcp.types as types

    _MCP_SDK_AVAILABLE = True
except ImportError:
    _MCP_SDK_AVAILABLE = False

SERVER_NAME = "autonomous-api-migration-engineer"
SERVER_VERSION = "0.1.0"

# ── Tool schemas (used by both SDK and fallback JSON-RPC handler) ─────────────

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "analyze_rest_endpoint",
        "description": (
            "Analyze a REST OpenAPI/Swagger spec and produce a detailed gRPC mapping analysis. "
            "Returns per-endpoint migration recommendations, RPC pattern advice, proto message "
            "field shapes, confidence scores, and phased rollout plan."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "openapi_path": {
                    "type": "string",
                    "description": "Filesystem path to the OpenAPI YAML or JSON spec file.",
                },
                "openapi_content": {
                    "type": "string",
                    "description": "Raw YAML or JSON content of the OpenAPI spec (alternative to openapi_path).",
                },
                "endpoint_id": {
                    "type": "string",
                    "description": (
                        "Optional. Filter analysis to a single endpoint, e.g. 'GET /users/{id}'. "
                        "Omit to analyze the entire service."
                    ),
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "generate_proto",
        "description": (
            "Generate proto3 file syntax for a REST service or a single endpoint. "
            "Returns complete .proto text with service definition, rpc methods, and "
            "request/response message blocks derived from the OpenAPI schema."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "openapi_path": {
                    "type": "string",
                    "description": "Filesystem path to the OpenAPI YAML or JSON spec file.",
                },
                "openapi_content": {
                    "type": "string",
                    "description": "Raw YAML or JSON content of the OpenAPI spec.",
                },
                "endpoint_id": {
                    "type": "string",
                    "description": (
                        "Optional. Generate a focused .proto for a single endpoint "
                        "(e.g. 'POST /users'). Omit for full service .proto."
                    ),
                },
                "output_path": {
                    "type": "string",
                    "description": "Optional. Write the .proto to this file path.",
                },
                "include_header_template": {
                    "type": "boolean",
                    "description": "If true (default), include the canonical proto header boilerplate.",
                    "default": True,
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "migrate_code",
        "description": (
            "Run the full REST-to-gRPC migration pipeline for a single endpoint — fully agentic, "
            "no human checkpoint. Scans the spec, plans the migration, generates a gRPC proposal, "
            "auto-approves it, then scaffolds the service implementation, stubs, and mapping tests. "
            "Returns all generated file paths and their contents for inline LLM review."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["endpoint_id"],
            "properties": {
                "endpoint_id": {
                    "type": "string",
                    "description": "The endpoint to migrate (e.g. 'POST /users'). Must be a gRPC candidate.",
                },
                "openapi_path": {
                    "type": "string",
                    "description": "Filesystem path to the OpenAPI YAML or JSON spec.",
                },
                "openapi_content": {
                    "type": "string",
                    "description": "Raw YAML or JSON content of the OpenAPI spec.",
                },
                "output_dir": {
                    "type": "string",
                    "description": "Root directory for generated files (default: build/mcp_migration).",
                    "default": "build/mcp_migration",
                },
                "memory_path": {
                    "type": "string",
                    "description": "Optional path to the migration memory JSONL store for RAG context.",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "generate_grpc_client",
        "description": (
            "Generate Python gRPC client stubs to replace old HTTP client calls. "
            "Parses a .proto text or a GrpcMigrationProposal JSON and emits a fully-typed "
            "Python client class with per-RPC method stubs, TLS options, channel lifecycle "
            "management, and a grpc_tools.protoc compile command."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "proto_content": {
                    "type": "string",
                    "description": "Raw proto3 text to generate the client from.",
                },
                "proposal_path": {
                    "type": "string",
                    "description": "Path to a GrpcMigrationProposal JSON file (alternative to proto_content).",
                },
                "module_name": {
                    "type": "string",
                    "description": "The proto module/file name for import paths (default: 'service').",
                    "default": "service",
                },
                "output_path": {
                    "type": "string",
                    "description": "Optional. Write the generated client to this .py file.",
                },
                "include_interceptors": {
                    "type": "boolean",
                    "description": "If true (default), include production interceptor boilerplate.",
                    "default": True,
                },
            },
            "additionalProperties": False,
        },
    },
]

# ── Tool dispatcher ───────────────────────────────────────────────────────────

_TOOL_FNS = {
    "analyze_rest_endpoint": analyze_rest_endpoint,
    "generate_proto": generate_proto,
    "migrate_code": migrate_code,
    "generate_grpc_client": generate_grpc_client,
}


def _call_tool(name: str, arguments: dict[str, Any]) -> Any:
    fn = _TOOL_FNS.get(name)
    if fn is None:
        raise ValueError(f"Unknown tool: '{name}'. Available: {list(_TOOL_FNS.keys())}")
    return fn(**arguments)


# ── SDK-based server (preferred) ─────────────────────────────────────────────

def _build_sdk_server() -> "Server":
    server = Server(SERVER_NAME)

    @server.list_tools()
    async def handle_list_tools() -> list["types.Tool"]:
        return [
            types.Tool(
                name=t["name"],
                description=t["description"],
                inputSchema=t["inputSchema"],
            )
            for t in TOOL_SCHEMAS
        ]

    @server.call_tool()
    async def handle_call_tool(
        name: str, arguments: dict[str, Any] | None
    ) -> list["types.TextContent"]:
        try:
            result = _call_tool(name, arguments or {})
            return [types.TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
        except Exception as exc:
            logger.exception("Tool %s failed", name)
            return [types.TextContent(type="text", text=json.dumps({"error": str(exc)}))]

    @server.list_resources()
    async def handle_list_resources() -> list["types.Resource"]:
        return [
            types.Resource(
                uri=r["uri"],  # type: ignore[arg-type]
                name=r["name"],
                description=r["description"],
                mimeType=r["mimeType"],
            )
            for r in list_resources()
        ]

    @server.read_resource()
    async def handle_read_resource(uri: "types.AnyUrl") -> str:
        resource = read_resource(str(uri))
        return resource["text"]

    return server


# ── Fallback: raw stdio JSON-RPC 2.0 handler ─────────────────────────────────

def _run_stdio_fallback() -> None:
    """
    Minimal JSON-RPC 2.0 stdio handler when the mcp SDK is not installed.
    Handles: initialize, tools/list, tools/call, resources/list, resources/read.
    """
    logger.info("mcp SDK not found — using built-in stdio JSON-RPC fallback.")

    def _send(obj: dict) -> None:
        sys.stdout.write(json.dumps(obj) + "\n")
        sys.stdout.flush()

    def _respond(req_id: Any, result: Any) -> None:
        _send({"jsonrpc": "2.0", "id": req_id, "result": result})

    def _error(req_id: Any, code: int, message: str) -> None:
        _send({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})

    for raw_line in sys.stdin:
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            req = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            _error(None, -32700, f"Parse error: {exc}")
            continue

        req_id = req.get("id")
        method = req.get("method", "")
        params = req.get("params", {})

        try:
            if method == "initialize":
                _respond(req_id, {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}, "resources": {}},
                    "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                })
            elif method == "tools/list":
                _respond(req_id, {"tools": TOOL_SCHEMAS})
            elif method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                result = _call_tool(tool_name, arguments)
                _respond(req_id, {
                    "content": [{"type": "text", "text": json.dumps(result, indent=2, default=str)}]
                })
            elif method == "resources/list":
                _respond(req_id, {"resources": list_resources()})
            elif method == "resources/read":
                uri = params.get("uri", "")
                resource = read_resource(uri)
                _respond(req_id, {
                    "contents": [{"uri": resource["uri"], "mimeType": resource["mimeType"], "text": resource["text"]}]
                })
            elif method == "notifications/initialized":
                pass  # No response needed for notifications
            else:
                _error(req_id, -32601, f"Method not found: {method}")
        except Exception as exc:
            logger.exception("Request %s failed", method)
            _error(req_id, -32603, str(exc))


# ── HTTP / SSE server ─────────────────────────────────────────────────────────

def _run_http(host: str, port: int) -> None:
    """Serve the MCP server over HTTP with SSE transport."""
    try:
        from fastapi import FastAPI, Request
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.responses import JSONResponse, StreamingResponse
        import asyncio
        import uvicorn
    except ImportError:
        print(
            "ERROR: FastAPI and uvicorn are required for HTTP mode.\n"
            "Install them with: pip install fastapi uvicorn",
            file=sys.stderr,
        )
        sys.exit(1)

    app = FastAPI(
        title=SERVER_NAME,
        description=__doc__,
        version=SERVER_VERSION,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── JSON-RPC endpoint ─────────────────────────────────────────────────────
    @app.post("/mcp")
    async def mcp_endpoint(request: Request) -> JSONResponse:
        try:
            req = await request.json()
        except Exception:
            return JSONResponse(
                {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}},
                status_code=400,
            )

        req_id = req.get("id")
        method = req.get("method", "")
        params = req.get("params", {})

        try:
            if method == "initialize":
                result = {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}, "resources": {}},
                    "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                }
            elif method == "tools/list":
                result = {"tools": TOOL_SCHEMAS}
            elif method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                tool_result = _call_tool(tool_name, arguments)
                result = {
                    "content": [
                        {"type": "text", "text": json.dumps(tool_result, indent=2, default=str)}
                    ]
                }
            elif method == "resources/list":
                result = {"resources": list_resources()}
            elif method == "resources/read":
                uri = params.get("uri", "")
                resource = read_resource(uri)
                result = {
                    "contents": [
                        {"uri": resource["uri"], "mimeType": resource["mimeType"], "text": resource["text"]}
                    ]
                }
            else:
                return JSONResponse(
                    {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method not found: {method}"}},
                )
        except Exception as exc:
            logger.exception("HTTP tool call failed")
            return JSONResponse(
                {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32603, "message": str(exc)}},
            )

        return JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": result})

    # ── SSE endpoint for streaming-capable hosts ──────────────────────────────
    @app.get("/sse")
    async def sse_endpoint(request: Request):
        async def event_stream():
            # Send server capabilities as the first SSE event
            init_event = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {
                    "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                    "capabilities": {"tools": {}, "resources": {}},
                },
            }
            yield f"data: {json.dumps(init_event)}\n\n"
            # Keep-alive
            while True:
                if await request.is_disconnected():
                    break
                import asyncio
                await asyncio.sleep(15)
                yield ": keep-alive\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # ── Health endpoint ───────────────────────────────────────────────────────
    @app.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok", "server": SERVER_NAME, "version": SERVER_VERSION})

    print(f"🚀  MCP server (HTTP+SSE) running at http://{host}:{port}")
    print(f"    POST  http://{host}:{port}/mcp      — JSON-RPC 2.0 endpoint")
    print(f"    GET   http://{host}:{port}/sse      — SSE event stream")
    print(f"    GET   http://{host}:{port}/health   — health check")
    uvicorn.run(app, host=host, port=port, log_level="info")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="migration-engineer-mcp",
        description="Autonomous API Migration Engineer — MCP Server",
    )
    parser.add_argument(
        "--http",
        action="store_true",
        help="Run in HTTP + SSE mode instead of stdio.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind in HTTP mode (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind in HTTP mode (default: 8000).",
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: WARNING).",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,  # Always log to stderr so stdout stays clean for JSON-RPC
    )

    if args.http:
        _run_http(args.host, args.port)
        return

    # ── stdio mode ────────────────────────────────────────────────────────────
    if _MCP_SDK_AVAILABLE:
        import asyncio
        import mcp.server.stdio

        server = _build_sdk_server()

        async def _run() -> None:
            async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
                init_opts = InitializationOptions(
                    server_name=SERVER_NAME,
                    server_version=SERVER_VERSION,
                    capabilities=server.get_capabilities(
                        notification_options=None,
                        experimental_capabilities={},
                    ),
                )
                await server.run(read_stream, write_stream, init_opts)

        asyncio.run(_run())
    else:
        _run_stdio_fallback()


if __name__ == "__main__":
    main()
