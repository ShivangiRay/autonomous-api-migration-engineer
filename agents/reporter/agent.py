from __future__ import annotations

from pathlib import Path

from libs.common.models import CompatibilityReport, GeneratedArtifact, MigrationPlan, ServiceInventory


class ReportingAgent:
    name = "reporter"

    def report(
        self,
        inventory: ServiceInventory,
        plan: MigrationPlan,
        compatibility: CompatibilityReport,
        artifacts: list[GeneratedArtifact],
        output_dir: str | Path,
    ) -> Path:
        root = Path(output_dir)
        report_path = root / "executive-report.md"
        lines = [
            f"# Migration Report: {inventory.service_name}",
            "",
            f"Readiness score: **{plan.readiness_score}**",
            f"Compatibility score: **{compatibility.score}**",
            "",
            "## Endpoint Inventory",
            "",
        ]
        for endpoint in inventory.endpoints:
            lines.append(f"- `{endpoint.method} {endpoint.path}`: {endpoint.summary or endpoint.operation_id}")
        lines.extend(["", "## Recommendations", ""])
        by_id = {endpoint.id: endpoint for endpoint in inventory.endpoints}
        for item in plan.recommendations:
            endpoint = by_id[item.endpoint_id]
            lines.append(
                f"- `{endpoint.method} {endpoint.path}` -> `{item.target.value}` "
                f"(confidence {item.confidence:.2f}). {item.rationale}"
            )
        lines.extend(["", "## Compatibility Risks", ""])
        if compatibility.findings:
            for finding in compatibility.findings:
                lines.append(f"- `{finding.endpoint_id}` [{finding.severity}]: {finding.message}")
        else:
            lines.append("- No compatibility risks detected in the deterministic bootstrap checks.")
        lines.extend(["", "## Artifacts", ""])
        for artifact in artifacts:
            lines.append(f"- `{artifact.artifact_type}`: `{artifact.path}` ({artifact.approval_status})")
        lines.extend(
            [
                "",
                "## Rollback Strategy",
                "",
                "Keep REST endpoints as source of truth until generated contracts pass review, compatibility checks, and dual-run validation.",
            ]
        )
        report_path.write_text("\n".join(lines))
        return report_path

