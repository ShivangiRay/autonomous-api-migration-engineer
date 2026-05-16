from __future__ import annotations

from libs.common.models import MigrationPlan, MigrationTarget, Recommendation, ServiceInventory


class ArchitecturePlannerAgent:
    name = "planner"

    def plan(self, inventory: ServiceInventory) -> MigrationPlan:
        recommendations: list[Recommendation] = []
        for endpoint in inventory.endpoints:
            target = self._classify(endpoint.method, endpoint.path, endpoint.operation_id)
            phase = 2 if target in {MigrationTarget.GRPC, MigrationTarget.EVENT} else 1
            confidence = 0.86 if target != MigrationTarget.SPLIT else 0.72
            recommendations.append(
                Recommendation(
                    endpoint_id=endpoint.id,
                    target=target,
                    phase=phase,
                    rationale=self._rationale(target, endpoint.path),
                    confidence=confidence,
                    impacted_dependencies=[endpoint.domain, "auth"] if endpoint.auth == "required" else [endpoint.domain],
                )
            )

        readiness = max(40, 95 - sum(1 for item in recommendations if item.target == MigrationTarget.SPLIT) * 8)
        phases = {
            "phase_1_analysis_only": [item.endpoint_id for item in recommendations],
            "phase_2_contract_proposal": [item.endpoint_id for item in recommendations if item.phase == 2],
            "phase_3_validation": [item.endpoint_id for item in recommendations if item.target != MigrationTarget.REST],
            "phase_4_migration_report": [item.endpoint_id for item in recommendations],
        }
        return MigrationPlan(
            service_name=inventory.service_name,
            recommendations=recommendations,
            readiness_score=readiness,
            rollout_phases=phases,
        )

    def _classify(self, method: str, path: str, operation_id: str) -> MigrationTarget:
        lowered = f"{method} {path} {operation_id}".lower()
        if "event" in lowered or "activate" in lowered or method in {"POST", "PATCH"} and "status" in lowered:
            return MigrationTarget.EVENT
        if method == "GET" and "users" in path and "{" not in path:
            return MigrationTarget.REST
        if "admin" in lowered:
            return MigrationTarget.SPLIT
        if method in {"GET", "POST", "PUT", "PATCH"}:
            return MigrationTarget.GRPC
        return MigrationTarget.REST

    def _rationale(self, target: MigrationTarget, path: str) -> str:
        reasons = {
            MigrationTarget.REST: "Collection-style read endpoint remains efficient and externally friendly as REST.",
            MigrationTarget.GRPC: "Request/response operation has typed DTOs and benefits from strongly versioned service contracts.",
            MigrationTarget.EVENT: "State transition should publish an asynchronous fact for downstream consumers.",
            MigrationTarget.SPLIT: "Endpoint crosses an administrative bounded context and should be separated before protocol migration.",
            MigrationTarget.DEPRECATE: "Endpoint overlaps newer capabilities and should be merged or retired.",
        }
        return f"{reasons[target]} Evidence: {path}."

