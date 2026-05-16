from __future__ import annotations

from pathlib import Path

from libs.common.models import ServiceInventory
from libs.parsers.openapi import parse_openapi


class ScannerAgent:
    name = "scanner"

    def scan(self, openapi_path: str | Path) -> ServiceInventory:
        inventory = parse_openapi(openapi_path)
        inventory.source_evidence.append(str(openapi_path))
        return inventory

