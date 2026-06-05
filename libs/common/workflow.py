from __future__ import annotations

import json
import shutil
from pathlib import Path

from agents.scanner.agent import ScannerAgent
from agents.planner.agent import ArchitecturePlannerAgent
from agents.contract_generator.agent import ContractGenerationAgent
from agents.verifier.agent import VerificationAgent
from agents.reporter.agent import ReportingAgent


class MigrationWorkflow:
    def __init__(
        self,
        use_llm: bool = False,
        llm_model: str | None = None,
        ollama_url: str | None = None,
        llm_timeout: float = 60.0,
    ) -> None:
        """
        Args:
            use_llm: Enable Ollama LLM-powered endpoint classification.
            llm_model: Ollama model name (e.g. "llama3.2", "mistral").
            ollama_url: Ollama server URL (default: http://localhost:11434).
            llm_timeout: Per-endpoint timeout for LLM calls in seconds.
        """
        self.scanner = ScannerAgent()
        self.planner = ArchitecturePlannerAgent(
            use_llm=use_llm,
            model=llm_model,
            ollama_url=ollama_url,
            timeout=llm_timeout,
        )
        self.generator = ContractGenerationAgent()
        self.verifier = VerificationAgent()
        self.reporter = ReportingAgent()

    def run(self, openapi_path: str | Path, output_dir: str | Path) -> dict:
        root = Path(output_dir)
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True)

        inventory = self.scanner.scan(openapi_path)
        (root / "endpoint-inventory.json").write_text(inventory.model_dump_json(indent=2))
        plan = self.planner.plan(inventory)
        (root / "migration-plan.json").write_text(plan.model_dump_json(indent=2))
        artifacts = self.generator.generate(inventory, plan, root)
        compatibility = self.verifier.verify(inventory, plan)
        (root / "compatibility-report.json").write_text(compatibility.model_dump_json(indent=2))
        report_path = self.reporter.report(inventory, plan, compatibility, artifacts, root)
        adr_dir = root / "adr"
        adr_dir.mkdir(exist_ok=True)
        (adr_dir / "0001-contract-migration-strategy.md").write_text(
            "# Contract Migration Strategy\n\nGenerated contracts remain draft artifacts until human approval.\n"
        )
        audit = [
            {"agent": "scanner", "output": "endpoint-inventory.json"},
            {"agent": "planner", "output": "migration-plan.json"},
            {"agent": "contract-generator", "output": [artifact.path for artifact in artifacts]},
            {"agent": "verifier", "output": "compatibility-report.json"},
            {"agent": "reporter", "output": str(report_path)},
        ]
        (root / "audit-trail.json").write_text(json.dumps(audit, indent=2))
        return {
            "inventory": inventory,
            "plan": plan,
            "compatibility": compatibility,
            "artifacts": artifacts,
            "report_path": str(report_path),
        }
