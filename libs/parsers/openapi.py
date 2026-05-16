from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

from libs.common.models import Endpoint, ServiceInventory


HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def load_openapi(path: str | Path) -> dict[str, Any]:
    spec_path = Path(path)
    raw = spec_path.read_text()
    if spec_path.suffix.lower() in {".yaml", ".yml"}:
        if yaml is None:
            raise RuntimeError("PyYAML is required for YAML OpenAPI files.")
        return yaml.safe_load(raw)
    return json.loads(raw)


def parse_openapi(path: str | Path) -> ServiceInventory:
    spec = load_openapi(path)
    service_name = spec.get("info", {}).get("title", "legacy-rest-service")
    security = spec.get("security", [])
    endpoints: list[Endpoint] = []

    for route, path_item in spec.get("paths", {}).items():
        for method, operation in path_item.items():
            if method.lower() not in HTTP_METHODS:
                continue
            operation_id = operation.get("operationId") or f"{method}_{route}".replace("/", "_")
            domain = route.strip("/").split("/")[0] or "root"
            request_schema = _request_schema(operation)
            response_schema = _response_schema(operation)
            endpoints.append(
                Endpoint(
                    id=f"{method.upper()} {route}",
                    method=method.upper(),
                    path=route,
                    operation_id=operation_id,
                    domain=domain,
                    summary=operation.get("summary", ""),
                    request_schema=request_schema,
                    response_schema=response_schema,
                    auth="required" if operation.get("security") or security else "none",
                    pagination=_has_pagination(operation),
                    idempotency=method.lower() in {"get", "put", "delete"},
                    evidence=[f"openapi:paths.{route}.{method}"],
                )
            )

    patterns = []
    if any(endpoint.pagination for endpoint in endpoints):
        patterns.append("pagination")
    if any(endpoint.auth == "required" for endpoint in endpoints):
        patterns.append("authenticated")

    return ServiceInventory(service_name=service_name, endpoints=endpoints, detected_patterns=patterns)


def _request_schema(operation: dict[str, Any]) -> dict[str, Any]:
    body = operation.get("requestBody", {}).get("content", {})
    for media in ("application/json", "application/problem+json"):
        schema = body.get(media, {}).get("schema")
        if schema:
            return schema
    return {}


def _response_schema(operation: dict[str, Any]) -> dict[str, Any]:
    responses = operation.get("responses", {})
    selected = responses.get("200") or responses.get("201") or responses.get("202") or {}
    content = selected.get("content", {})
    return content.get("application/json", {}).get("schema", {})


def _has_pagination(operation: dict[str, Any]) -> bool:
    names = {param.get("name") for param in operation.get("parameters", [])}
    return bool({"page", "pageSize", "limit", "offset", "cursor"} & names)

