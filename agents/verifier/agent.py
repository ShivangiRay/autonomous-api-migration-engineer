from __future__ import annotations

from libs.common.models import CompatibilityFinding, CompatibilityReport, MigrationPlan, MigrationTarget, ServiceInventory


class VerificationAgent:
    name = "verifier"

    def verify(self, inventory: ServiceInventory, plan: MigrationPlan) -> CompatibilityReport:
        recommendations = {item.endpoint_id: item for item in plan.recommendations}
        findings: list[CompatibilityFinding] = []
        for endpoint in inventory.endpoints:
            recommendation = recommendations[endpoint.id]
            if recommendation.target == MigrationTarget.GRPC and endpoint.pagination:
                findings.append(
                    CompatibilityFinding(
                        endpoint_id=endpoint.id,
                        severity="medium",
                        message="Pagination semantics must be explicitly modeled in proto request and response messages.",
                        evidence=endpoint.evidence,
                    )
                )
            if recommendation.target == MigrationTarget.EVENT and not endpoint.idempotency:
                findings.append(
                    CompatibilityFinding(
                        endpoint_id=endpoint.id,
                        severity="high",
                        message="Event conversion needs idempotency key and duplicate handling strategy.",
                        evidence=endpoint.evidence,
                    )
                )
        penalty = sum(15 if item.severity == "high" else 7 for item in findings)
        return CompatibilityReport(service_name=inventory.service_name, score=max(1, 100 - penalty), findings=findings)

