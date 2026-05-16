from __future__ import annotations

from libs.common.models import MigrationPlan, MigrationTarget, ServiceInventory


def render_asyncapi(inventory: ServiceInventory, plan: MigrationPlan) -> dict:
    event_ids = {item.endpoint_id for item in plan.recommendations if item.target == MigrationTarget.EVENT}
    channels = {}
    schemas = {}
    for endpoint in inventory.endpoints:
        if endpoint.id not in event_ids:
            continue
        event_name = endpoint.operation_id[0].upper() + endpoint.operation_id[1:] + "Event"
        channel = f"{endpoint.domain}.{endpoint.operation_id}.v1"
        channels[channel] = {
            "publish": {
                "message": {
                    "name": event_name,
                    "payload": {"$ref": f"#/components/schemas/{event_name}"},
                }
            }
        }
        schemas[event_name] = {
            "type": "object",
            "required": ["eventId", "occurredAt", "provenance"],
            "properties": {
                "eventId": {"type": "string"},
                "occurredAt": {"type": "string", "format": "date-time"},
                "provenance": {"type": "object"},
                "payload": {"type": "object"},
            },
        }
    return {
        "asyncapi": "2.6.0",
        "info": {"title": f"{inventory.service_name} Events", "version": "1.0.0"},
        "channels": channels,
        "components": {"schemas": schemas},
    }

