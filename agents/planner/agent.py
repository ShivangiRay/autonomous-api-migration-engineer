"""
Architecture Planner Agent.

Classifies each REST endpoint in a ServiceInventory and produces a
MigrationPlan with per-endpoint Recommendations.

Two modes:
  deterministic (default) — fast, rule-based, no external dependencies
  LLM (opt-in)            — uses a local Ollama model for richer reasoning;
                            falls back to deterministic on any failure

Usage:
    # Deterministic (original behaviour)
    planner = ArchitecturePlannerAgent()

    # LLM-powered
    planner = ArchitecturePlannerAgent(use_llm=True, model="llama3.2")

    # Both modes produce the same MigrationPlan interface
    plan = planner.plan(inventory)
"""
from __future__ import annotations

import logging
import os

from libs.common.models import MigrationPlan, MigrationTarget, Recommendation, ServiceInventory

logger = logging.getLogger(__name__)


class ArchitecturePlannerAgent:
    name = "planner"

    def __init__(
        self,
        use_llm: bool | None = None,
        model: str | None = None,
        ollama_url: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        """
        Args:
            use_llm: Enable LLM-powered classification via Ollama.
                     Defaults to the MIGRATION_USE_LLM env var, then False.
            model: Ollama model name (e.g. "llama3.2", "mistral", "phi3:mini").
                   Defaults to OLLAMA_MODEL env var, then "llama3.2".
            ollama_url: Base URL for the Ollama server.
                        Defaults to OLLAMA_URL env var, then "http://localhost:11434".
            timeout: Seconds to wait for each Ollama response (default 60s).
        """
        if use_llm is None:
            use_llm = os.environ.get("MIGRATION_USE_LLM", "").lower() in {"1", "true", "yes"}
        self._use_llm = use_llm
        self._model = model
        self._ollama_url = ollama_url
        self._timeout = timeout
        self._llm_agent = None  # lazy-initialised

    # ── Public interface ──────────────────────────────────────────────────────

    def plan(self, inventory: ServiceInventory) -> MigrationPlan:
        """Produce a MigrationPlan for the given ServiceInventory."""
        if self._use_llm:
            logger.info(
                "LLM planner active (model=%s, url=%s)",
                self._model or os.environ.get("OLLAMA_MODEL", "llama3.2"),
                self._ollama_url or os.environ.get("OLLAMA_URL", "http://localhost:11434"),
            )
        recommendations: list[Recommendation] = []
        for endpoint in inventory.endpoints:
            target, confidence, rationale = self._decide(endpoint)
            phase = 2 if target in {MigrationTarget.GRPC, MigrationTarget.EVENT} else 1
            recommendations.append(
                Recommendation(
                    endpoint_id=endpoint.id,
                    target=target,
                    phase=phase,
                    rationale=rationale,
                    confidence=confidence,
                    impacted_dependencies=(
                        [endpoint.domain, "auth"] if endpoint.auth == "required" else [endpoint.domain]
                    ),
                )
            )

        readiness = max(40, 95 - sum(1 for r in recommendations if r.target == MigrationTarget.SPLIT) * 8)
        phases = {
            "phase_1_analysis_only": [r.endpoint_id for r in recommendations],
            "phase_2_contract_proposal": [r.endpoint_id for r in recommendations if r.phase == 2],
            "phase_3_validation": [r.endpoint_id for r in recommendations if r.target != MigrationTarget.REST],
            "phase_4_migration_report": [r.endpoint_id for r in recommendations],
        }
        return MigrationPlan(
            service_name=inventory.service_name,
            recommendations=recommendations,
            readiness_score=readiness,
            rollout_phases=phases,
        )

    # ── Internal dispatch ─────────────────────────────────────────────────────

    def _decide(self, endpoint) -> tuple[MigrationTarget, float, str]:
        """Return (target, confidence, rationale) for one endpoint."""
        if self._use_llm:
            decision = self._llm_agent_instance().classify(endpoint)
            return decision.target, decision.confidence, decision.rationale
        # Deterministic path
        target = self._classify(endpoint.method, endpoint.path, endpoint.operation_id)
        confidence = 0.72 if target == MigrationTarget.SPLIT else 0.86
        return target, confidence, self._rationale(target, endpoint.path)

    def _llm_agent_instance(self):
        """Lazy-initialise the LLM agent (avoids importing httpx unless needed)."""
        if self._llm_agent is None:
            from agents.planner.llm_planner import LLMArchitecturePlannerAgent
            self._llm_agent = LLMArchitecturePlannerAgent(
                model=self._model,
                ollama_url=self._ollama_url,
                timeout=self._timeout,
            )
        return self._llm_agent

    # ── Deterministic classifier (unchanged, also used as fallback) ───────────

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
