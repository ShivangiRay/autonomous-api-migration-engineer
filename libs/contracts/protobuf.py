from __future__ import annotations

import re

from libs.common.models import MigrationPlan, MigrationTarget, ServiceInventory


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


def _pascal(value: str) -> str:
    return "".join(part.capitalize() for part in re.split(r"[^a-zA-Z0-9]+", value) if part)

