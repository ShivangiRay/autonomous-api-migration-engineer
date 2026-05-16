from __future__ import annotations

import json
from pathlib import Path

from libs.common.models import GeneratedArtifact, MigrationPlan, ServiceInventory
from libs.contracts.events import render_asyncapi
from libs.contracts.protobuf import render_proto


class ContractGenerationAgent:
    name = "contract-generator"

    def generate(self, inventory: ServiceInventory, plan: MigrationPlan, output_dir: str | Path) -> list[GeneratedArtifact]:
        root = Path(output_dir)
        contracts = root / "contracts"
        events = root / "events"
        contracts.mkdir(parents=True, exist_ok=True)
        events.mkdir(parents=True, exist_ok=True)

        proto_path = contracts / "user_service.proto"
        event_path = events / "user-events.asyncapi.json"
        if proto_path.exists() or event_path.exists():
            raise FileExistsError("Generated contracts already exist; refusing to silently overwrite.")

        proto_path.write_text(render_proto(inventory, plan))
        event_path.write_text(json.dumps(render_asyncapi(inventory, plan), indent=2))
        provenance = {"source": "scanner+planner", "service": inventory.service_name, "requires_approval": True}
        return [
            GeneratedArtifact(artifact_type="protobuf", path=str(proto_path), provenance=provenance),
            GeneratedArtifact(artifact_type="asyncapi", path=str(event_path), provenance=provenance),
        ]

