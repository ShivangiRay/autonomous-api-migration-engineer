from __future__ import annotations

import json
import re
from pathlib import Path

from libs.common.models import Endpoint, MemoryCase


DEFAULT_MEMORY_PATH = Path("build/memory/migration-memory.jsonl")


class MigrationMemoryStore:
    def __init__(self, path: str | Path = DEFAULT_MEMORY_PATH) -> None:
        self.path = Path(path)

    def add(self, case: MemoryCase) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        existing_ids = {item.id for item in self.all()}
        if case.id in existing_ids:
            return
        with self.path.open("a") as handle:
            handle.write(case.model_dump_json() + "\n")

    def all(self) -> list[MemoryCase]:
        if not self.path.exists():
            return []
        return [MemoryCase(**json.loads(line)) for line in self.path.read_text().splitlines() if line.strip()]

    def similar(self, endpoint: Endpoint, target: str, limit: int = 3) -> list[MemoryCase]:
        query_tokens = _tokens(" ".join([endpoint.id, endpoint.operation_id, endpoint.domain, target]))
        scored: list[tuple[int, MemoryCase]] = []
        for case in self.all():
            case_tokens = _tokens(" ".join([case.endpoint_id, case.target, case.rationale, " ".join(case.tags)]))
            score = len(query_tokens & case_tokens)
            if score:
                scored.append((score, case))
        return [case for _, case in sorted(scored, key=lambda item: item[0], reverse=True)[:limit]]


def _tokens(value: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[a-zA-Z0-9]+", value) if len(token) > 2}
