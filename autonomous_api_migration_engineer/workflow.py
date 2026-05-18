from __future__ import annotations

from pathlib import Path
from typing import Any

from libs.common.workflow import MigrationWorkflow


def run_migration(openapi_path: str | Path, output_dir: str | Path = "build/artifacts") -> dict[str, Any]:
    """Run the full migration analysis workflow for an OpenAPI spec."""

    return MigrationWorkflow().run(openapi_path, output_dir)

