"""
LLM-powered architecture planner using a local Ollama model.

Replaces the deterministic rule-based classifier with a reasoning LLM
that evaluates each REST endpoint in full context and decides the best
migration target (gRPC / event-driven / keep REST / split / deprecate).

Ollama must be running locally:
    ollama serve
    ollama pull llama3.2    # or mistral, phi3:mini, gemma2:2b, etc.

If Ollama is unreachable or returns malformed output, every method
gracefully falls back to the deterministic classifier — the system
never crashes due to LLM unavailability.

Environment variables (all overridden by constructor args):
    OLLAMA_URL    — default: http://localhost:11434
    OLLAMA_MODEL  — default: llama3.2
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from libs.common.models import Endpoint, MigrationTarget

logger = logging.getLogger(__name__)

# ── Pydantic model for validating LLM JSON output ────────────────────────────

class LLMDecision(BaseModel):
    """Structured output expected from the LLM for each endpoint."""

    target: MigrationTarget
    confidence: float = Field(default=0.80, ge=0.0, le=1.0)
    rationale: str = Field(default="LLM-generated rationale.")

    model_config = {"use_enum_values": False}


# ── System prompt ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a senior API architect and migration expert.
Your task is to analyse a single REST API endpoint and decide the best
migration strategy as part of a REST-to-modern-architecture migration project.

You must classify the endpoint into EXACTLY ONE of these targets:
  - migrate_grpc      : Request/response pattern with typed DTOs. Benefits from
                        strongly versioned binary contracts, low latency service
                        calls, and bidirectional streaming. Use when the caller
                        is another internal backend service, not a browser.
  - convert_event     : The endpoint represents a state transition or domain
                        event (e.g. "activate", "disable", "status changed").
                        Better modelled as an async published event consumed
                        by downstream services via Kafka or RabbitMQ.
  - keep_rest         : Endpoint is externally facing (browser, mobile, partner
                        API), or is a simple collection read where REST+JSON
                        is the most natural and widely understood interface.
  - split_context     : The endpoint crosses multiple bounded contexts or
                        mixes concerns (e.g. an "admin" endpoint that does
                        both user management and billing). Must be decomposed
                        into smaller, focused services before protocol migration.
  - deprecate_or_merge: The endpoint duplicates functionality already provided
                        by a newer endpoint, or represents a deprecated feature
                        that should be retired rather than migrated.

Consider ALL of the following signals:
  - HTTP method: GET (query), POST (command/create), PUT/PATCH (update), DELETE
  - Path semantics: resource hierarchy, path parameters, collection vs item
  - Operation name: createX, updateX, activateX, deleteX, listX, searchX
  - Summary / description: any business context clues
  - Request schema: what data is sent (typed DTOs → gRPC, simple IDs → keep REST)
  - Response schema: what data is returned
  - Auth: authenticated endpoints are usually internal service calls (→ gRPC)
  - Pagination: paginated list endpoints are often best kept as REST
  - Idempotency: PUT/DELETE are idempotent (important for gRPC retry safety)
  - Domain: which bounded context does this endpoint belong to

You MUST respond with ONLY a valid JSON object — no preamble, no explanation
outside the JSON, no markdown code fences. The JSON must have exactly these keys:

{
  "target": "<one of: migrate_grpc | convert_event | keep_rest | split_context | deprecate_or_merge>",
  "confidence": <float between 0.0 and 1.0>,
  "rationale": "<one concise paragraph explaining the reasoning>"
}
"""


# ── Prompt builder ────────────────────────────────────────────────────────────

def _build_user_message(endpoint: Endpoint) -> str:
    """Format an endpoint as a structured prompt message for the LLM."""
    req = _summarise_schema(endpoint.request_schema)
    resp = _summarise_schema(endpoint.response_schema)
    return f"""\
Analyse this REST endpoint and decide its migration strategy.

HTTP Method   : {endpoint.method}
Path          : {endpoint.path}
Operation ID  : {endpoint.operation_id}
Summary       : {endpoint.summary or "(none provided)"}
Domain        : {endpoint.domain}
Auth Required : {endpoint.auth}
Pagination    : {"yes" if endpoint.pagination else "no"}
Idempotent    : {"yes" if endpoint.idempotency else "no"}
Request Schema: {req}
Response Schema: {resp}
Evidence      : {", ".join(endpoint.evidence) or "(none)"}

Respond ONLY with a JSON object as described in the system prompt.
"""


def _summarise_schema(schema: dict) -> str:
    """Summarise a JSON Schema dict as a compact human-readable string."""
    if not schema:
        return "(empty / none)"
    ref = schema.get("$ref")
    if ref:
        return f"$ref: {ref.rsplit('/', 1)[-1]}"
    props = schema.get("properties", {})
    if props:
        fields = ", ".join(
            f"{name}: {prop.get('type', 'any')}" for name, prop in list(props.items())[:8]
        )
        extra = f" ... (+{len(props) - 8} more)" if len(props) > 8 else ""
        return "{" + fields + extra + "}"
    t = schema.get("type")
    return t if t else json.dumps(schema)[:120]


# ── Main LLM planner class ────────────────────────────────────────────────────

class LLMArchitecturePlannerAgent:
    """
    Classifies REST endpoints using a local Ollama LLM.

    Falls back to the deterministic classifier transparently on any failure
    (Ollama not running, timeout, malformed JSON, validation error).
    """

    name = "llm-planner"

    def __init__(
        self,
        model: str | None = None,
        ollama_url: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.model = model or os.environ.get("OLLAMA_MODEL", "llama3.2")
        self.ollama_url = (ollama_url or os.environ.get("OLLAMA_URL", "http://localhost:11434")).rstrip("/")
        self.timeout = timeout
        self._client: Any = None  # lazy-initialised httpx client

    # ── Public method ─────────────────────────────────────────────────────────

    def classify(self, endpoint: Endpoint) -> LLMDecision:
        """
        Ask the LLM to classify one endpoint.

        Returns an LLMDecision. On any failure, returns a decision produced
        by the deterministic fallback so callers never see an exception.
        """
        try:
            raw = self._call_ollama(endpoint)
            return self._parse_response(raw, endpoint)
        except _OllamaUnavailableError as exc:
            logger.warning(
                "Ollama unavailable (%s) — falling back to deterministic classifier for %s",
                exc, endpoint.id,
            )
            return self._deterministic_fallback(endpoint)
        except Exception as exc:
            logger.warning(
                "LLM classification failed (%s: %s) — falling back for %s",
                type(exc).__name__, exc, endpoint.id,
            )
            return self._deterministic_fallback(endpoint)

    # ── Ollama HTTP call ──────────────────────────────────────────────────────

    def _call_ollama(self, endpoint: Endpoint) -> str:
        """POST to Ollama /api/chat and return the raw response text."""
        try:
            import httpx
        except ImportError as exc:
            raise _OllamaUnavailableError("httpx is not installed") from exc

        payload = {
            "model": self.model,
            "format": "json",
            "stream": False,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_message(endpoint)},
            ],
            "options": {
                "temperature": 0.1,   # low temperature = more deterministic / consistent
                "num_predict": 300,   # enough for the JSON response, not too verbose
            },
        }

        try:
            response = httpx.post(
                f"{self.ollama_url}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.ConnectError as exc:
            raise _OllamaUnavailableError(f"Cannot connect to Ollama at {self.ollama_url}") from exc
        except httpx.TimeoutException as exc:
            raise _OllamaUnavailableError(f"Ollama timed out after {self.timeout}s") from exc
        except httpx.HTTPStatusError as exc:
            raise _OllamaUnavailableError(f"Ollama HTTP {exc.response.status_code}") from exc

        data = response.json()
        content = data.get("message", {}).get("content", "")
        if not content:
            raise ValueError("Ollama returned an empty message content.")
        return content

    # ── Response parsing ──────────────────────────────────────────────────────

    def _parse_response(self, raw: str, endpoint: Endpoint) -> LLMDecision:
        """
        Parse and validate the LLM JSON response.

        Tries to extract a JSON object even if the model wrapped it in
        markdown fences or added surrounding text.
        """
        # Strip markdown code fences if present
        cleaned = raw.strip()
        if "```" in cleaned:
            # Extract content between fences
            match = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
            cleaned = match.group(1).strip() if match else cleaned.replace("```", "").strip()

        # Find the first JSON object in the string
        brace_match = re.search(r"\{[\s\S]*\}", cleaned)
        if not brace_match:
            raise ValueError(f"No JSON object found in LLM response: {cleaned[:200]!r}")

        try:
            parsed = json.loads(brace_match.group())
        except json.JSONDecodeError as exc:
            raise ValueError(f"LLM returned invalid JSON: {exc}") from exc

        # Normalise target value — LLM might return "gRPC" instead of "migrate_grpc"
        if "target" in parsed:
            parsed["target"] = _normalise_target(parsed["target"])

        # Clamp confidence to [0, 1]
        if "confidence" in parsed:
            parsed["confidence"] = max(0.0, min(1.0, float(parsed["confidence"])))

        try:
            decision = LLMDecision(**parsed)
        except (ValidationError, TypeError) as exc:
            raise ValueError(f"LLM JSON failed Pydantic validation: {exc}") from exc

        logger.debug(
            "LLM classified %s → %s (confidence=%.2f)",
            endpoint.id, decision.target.value, decision.confidence,
        )
        return decision

    # ── Deterministic fallback ────────────────────────────────────────────────

    def _deterministic_fallback(self, endpoint: Endpoint) -> LLMDecision:
        """Mirror the original rule-based classifier as a last-resort fallback."""
        lowered = f"{endpoint.method} {endpoint.path} {endpoint.operation_id}".lower()
        if "event" in lowered or "activate" in lowered or (
            endpoint.method in {"POST", "PATCH"} and "status" in lowered
        ):
            target = MigrationTarget.EVENT
        elif endpoint.method == "GET" and "users" in endpoint.path and "{" not in endpoint.path:
            target = MigrationTarget.REST
        elif "admin" in lowered:
            target = MigrationTarget.SPLIT
        elif endpoint.method in {"GET", "POST", "PUT", "PATCH"}:
            target = MigrationTarget.GRPC
        else:
            target = MigrationTarget.REST

        confidence = 0.72 if target == MigrationTarget.SPLIT else 0.86
        rationale_map = {
            MigrationTarget.REST: "Collection-style read endpoint remains efficient and externally friendly as REST.",
            MigrationTarget.GRPC: "Request/response operation has typed DTOs and benefits from strongly versioned service contracts.",
            MigrationTarget.EVENT: "State transition should publish an asynchronous fact for downstream consumers.",
            MigrationTarget.SPLIT: "Endpoint crosses an administrative bounded context and should be separated before protocol migration.",
            MigrationTarget.DEPRECATE: "Endpoint overlaps newer capabilities and should be merged or retired.",
        }
        return LLMDecision(
            target=target,
            confidence=confidence,
            rationale=f"{rationale_map[target]} Evidence: {endpoint.path}. [deterministic fallback]",
        )


# ── Target normaliser ─────────────────────────────────────────────────────────

_TARGET_ALIASES: dict[str, str] = {
    # Common LLM variations → canonical enum values
    "grpc": "migrate_grpc",
    "migrate_grpc": "migrate_grpc",
    "migrate-grpc": "migrate_grpc",
    "grpc_migration": "migrate_grpc",
    "event": "convert_event",
    "convert_event": "convert_event",
    "event_driven": "convert_event",
    "event-driven": "convert_event",
    "async": "convert_event",
    "rest": "keep_rest",
    "keep_rest": "keep_rest",
    "keep-rest": "keep_rest",
    "keep rest": "keep_rest",
    "retain_rest": "keep_rest",
    "split": "split_context",
    "split_context": "split_context",
    "split-context": "split_context",
    "deprecate": "deprecate_or_merge",
    "deprecate_or_merge": "deprecate_or_merge",
    "merge": "deprecate_or_merge",
    "retire": "deprecate_or_merge",
}


def _normalise_target(raw: str) -> str:
    """Normalise LLM target output to a canonical MigrationTarget enum value."""
    key = raw.strip().lower().replace(" ", "_")
    return _TARGET_ALIASES.get(key, key)


# ── Custom exception ──────────────────────────────────────────────────────────

class _OllamaUnavailableError(Exception):
    """Raised when Ollama cannot be reached (not a logic error — triggers fallback)."""
