from pathlib import Path

from libs.common.workflow import MigrationWorkflow
from libs.parsers.openapi import parse_openapi


FIXTURE = Path("examples/sample-openapi/user-management.openapi.json")


def test_openapi_parser_builds_inventory() -> None:
    inventory = parse_openapi(FIXTURE)
    assert inventory.service_name == "User Management API"
    assert len(inventory.endpoints) == 5
    assert any(endpoint.pagination for endpoint in inventory.endpoints)


def test_full_workflow_generates_artifacts(tmp_path: Path) -> None:
    result = MigrationWorkflow().run(FIXTURE, tmp_path)
    assert result["plan"].readiness_score >= 70
    assert (tmp_path / "endpoint-inventory.json").exists()
    assert (tmp_path / "migration-plan.json").exists()
    assert (tmp_path / "contracts" / "user_service.proto").exists()
    assert (tmp_path / "events" / "user-events.asyncapi.json").exists()
    assert "Migration Report" in (tmp_path / "executive-report.md").read_text()

