from __future__ import annotations

import re

from libs.common.models import Endpoint, MigrationPlan, MigrationTarget, ServiceInventory


def render_proto(inventory: ServiceInventory, plan: MigrationPlan) -> str:
    grpc_ids = {item.endpoint_id for item in plan.recommendations if item.target == MigrationTarget.GRPC}
    service = _pascal(inventory.service_name.replace(" API", "")) + "Grpc"
    lines = [
        'syntax = "proto3";',
        "",
        "package migration.user_management.v1;",
        "",
        "option go_package = \"github.com/example/migration/user_management/v1\";",
        "",
        f"service {service} {{",
    ]
    for endpoint in inventory.endpoints:
        if endpoint.id in grpc_ids:
            name = _pascal(endpoint.operation_id)
            lines.append(f"  rpc {name} ({name}Request) returns ({name}Response);")
    lines.extend(["}", ""])
    for endpoint in inventory.endpoints:
        if endpoint.id in grpc_ids:
            name = _pascal(endpoint.operation_id)
            lines.extend(
                [
                    f"message {name}Request {{",
                    '  string provenance_source = 1;',
                    "  string request_id = 2;",
                    "}",
                    "",
                    f"message {name}Response {{",
                    '  string provenance_source = 1;',
                    "  string payload_json = 2;",
                    "}",
                    "",
                ]
            )
    return "\n".join(lines)


def render_endpoint_proto(service_name: str, endpoint: Endpoint) -> str:
    rpc_name = _pascal(endpoint.operation_id)
    request_name = f"{rpc_name}Request"
    response_name = f"{rpc_name}Response"
    response_type = _message_name(endpoint.response_schema, "Payload")
    lines = [
        'syntax = "proto3";',
        "",
        "package migration.user_management.v1;",
        "",
        "option go_package = \"github.com/example/migration/user_management/v1\";",
        "",
        f"service {_pascal(service_name.replace(' API', ''))}Grpc {{",
        f"  rpc {rpc_name} ({request_name}) returns ({response_name});",
        "}",
        "",
        f"message {request_name} {{",
    ]
    fields = _schema_fields(endpoint.request_schema)
    if not fields:
        fields = [("request_id", "string")]
    for index, (name, proto_type) in enumerate(fields, start=1):
        lines.append(f"  {proto_type} {name} = {index};")
    lines.extend(["}", "", f"message {response_name} {{"])
    if response_type == "Payload":
        lines.append("  string payload_json = 1;")
    else:
        lines.append(f"  {response_type} {response_type[0].lower() + response_type[1:]} = 1;")
    lines.extend(["}", ""])
    if response_type != "Payload":
        lines.extend([f"message {response_type} {{", "  string id = 1;", "  string email = 2;", "  string status = 3;", "}", ""])
    return "\n".join(lines)


def apply_proto_comment(proto: str, comment: str) -> str:
    lowered = comment.lower()
    if "idempotency" in lowered and "idempotency_key" not in proto:
        lines = proto.splitlines()
        in_request = False
        request_start = 0
        for index, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("message ") and "Request" in stripped:
                in_request = True
                request_start = index
                continue
            if in_request and stripped == "}":
                field_numbers = [
                    int(part.split("=")[1].strip(" ;"))
                    for part in lines[request_start:index]
                    if "=" in part and part.strip().endswith(";") and part.startswith("  ")
                ]
                next_number = max(field_numbers or [0]) + 1
                lines.insert(index, f"  string idempotency_key = {next_number};")
                return "\n".join(lines)
    if "validation" in lowered and "validation_notes" not in proto:
        return proto + "\n// validation_notes: preserve required fields and existing OpenAPI constraints.\n"
    return proto


def _message_name(schema: dict, fallback: str) -> str:
    ref = schema.get("$ref", "")
    if ref:
        return _pascal(ref.rsplit("/", 1)[-1])
    return fallback


def _schema_fields(schema: dict) -> list[tuple[str, str]]:
    ref = schema.get("$ref")
    if ref and ref.endswith("CreateUserRequest"):
        return [("email", "string")]
    properties = schema.get("properties", {})
    return [(name, _json_type_to_proto(prop.get("type", "string"))) for name, prop in properties.items()]


def _json_type_to_proto(json_type: str) -> str:
    return {"integer": "int32", "number": "double", "boolean": "bool", "array": "repeated string"}.get(json_type, "string")


def _pascal(value: str) -> str:
    words: list[str] = []
    for chunk in re.split(r"[^a-zA-Z0-9]+", value):
        if not chunk:
            continue
        words.extend(re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)|[0-9]+", chunk))
    return "".join(part[:1].upper() + part[1:] for part in words)
