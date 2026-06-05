"""
Tests for LLMArchitecturePlannerAgent and the LLM path in ArchitecturePlannerAgent.

All tests mock the httpx call so no real Ollama server is needed in CI.
The mocking approach patches httpx.post to return a pre-canned response,
isolating our parsing + validation logic from the network.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agents.planner.agent import ArchitecturePlannerAgent
from agents.planner.llm_planner import (
    LLMArchitecturePlannerAgent,
    LLMDecision,
    _build_user_message,
    _normalise_target,
    _OllamaUnavailableError,
)
from libs.common.models import Endpoint, MigrationTarget

# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_endpoint(method="POST", path="/users", operation_id="createUser") -> Endpoint:
    return Endpoint(
        id=f"{method} {path}",
        method=method,
        path=path,
        operation_id=operation_id,
        summary="Test endpoint",
        domain="users",
        auth="required",
        pagination=False,
        idempotency=False,
        request_schema={"type": "object", "properties": {"email": {"type": "string"}}},
        response_schema={"type": "object", "properties": {"id": {"type": "string"}}},
        evidence=["POST /users"],
    )


def _mock_ollama_response(target: str, confidence: float = 0.92, rationale: str = "LLM says so."):
    """Create a mock httpx response that looks like an Ollama /api/chat response."""
    body = json.dumps({
        "message": {
            "role": "assistant",
            "content": json.dumps({
                "target": target,
                "confidence": confidence,
                "rationale": rationale,
            }),
        }
    })
    mock_resp = MagicMock()
    mock_resp.json.return_value = json.loads(body)
    mock_resp.raise_for_status.return_value = None
    return mock_resp


# ── _normalise_target ─────────────────────────────────────────────────────────

class TestNormaliseTarget:
    def test_canonical_grpc(self):
        assert _normalise_target("migrate_grpc") == "migrate_grpc"

    def test_alias_grpc(self):
        assert _normalise_target("gRPC") == "migrate_grpc"
        assert _normalise_target("grpc") == "migrate_grpc"
        assert _normalise_target("migrate-grpc") == "migrate_grpc"

    def test_canonical_event(self):
        assert _normalise_target("convert_event") == "convert_event"
        assert _normalise_target("event") == "convert_event"
        assert _normalise_target("event-driven") == "convert_event"

    def test_canonical_rest(self):
        assert _normalise_target("keep_rest") == "keep_rest"
        assert _normalise_target("keep rest") == "keep_rest"
        assert _normalise_target("rest") == "keep_rest"

    def test_canonical_split(self):
        assert _normalise_target("split_context") == "split_context"
        assert _normalise_target("split") == "split_context"

    def test_canonical_deprecate(self):
        assert _normalise_target("deprecate_or_merge") == "deprecate_or_merge"
        assert _normalise_target("deprecate") == "deprecate_or_merge"
        assert _normalise_target("retire") == "deprecate_or_merge"

    def test_unknown_passes_through(self):
        assert _normalise_target("something_new") == "something_new"


# ── _build_user_message ───────────────────────────────────────────────────────

class TestBuildUserMessage:
    def test_includes_method_and_path(self):
        ep = _make_endpoint("DELETE", "/orders/{id}", "deleteOrder")
        msg = _build_user_message(ep)
        assert "DELETE" in msg
        assert "/orders/{id}" in msg

    def test_includes_operation_id(self):
        ep = _make_endpoint()
        msg = _build_user_message(ep)
        assert "createUser" in msg

    def test_includes_schema_field(self):
        ep = _make_endpoint()
        msg = _build_user_message(ep)
        assert "email" in msg

    def test_includes_auth_info(self):
        ep = _make_endpoint()
        msg = _build_user_message(ep)
        assert "required" in msg

    def test_no_schema_shows_empty(self):
        ep = _make_endpoint()
        ep.request_schema = {}
        msg = _build_user_message(ep)
        assert "(empty / none)" in msg


# ── LLMArchitecturePlannerAgent ───────────────────────────────────────────────

class TestLLMArchitecturePlannerAgent:

    def test_classify_grpc_endpoint(self):
        agent = LLMArchitecturePlannerAgent(model="llama3.2")
        mock_resp = _mock_ollama_response("migrate_grpc", 0.93, "Strongly typed DTOs → gRPC.")
        with patch("httpx.post", return_value=mock_resp):
            decision = agent.classify(_make_endpoint())
        assert decision.target == MigrationTarget.GRPC
        assert decision.confidence == pytest.approx(0.93)
        assert "gRPC" in decision.rationale

    def test_classify_event_endpoint(self):
        agent = LLMArchitecturePlannerAgent()
        mock_resp = _mock_ollama_response("convert_event", 0.88, "State transition → event.")
        with patch("httpx.post", return_value=mock_resp):
            decision = agent.classify(_make_endpoint("PATCH", "/users/{id}/activate", "activateUser"))
        assert decision.target == MigrationTarget.EVENT

    def test_classify_keep_rest(self):
        agent = LLMArchitecturePlannerAgent()
        mock_resp = _mock_ollama_response("keep_rest", 0.80)
        with patch("httpx.post", return_value=mock_resp):
            decision = agent.classify(_make_endpoint("GET", "/users", "listUsers"))
        assert decision.target == MigrationTarget.REST

    def test_classify_split_context(self):
        agent = LLMArchitecturePlannerAgent()
        mock_resp = _mock_ollama_response("split_context", 0.70)
        with patch("httpx.post", return_value=mock_resp):
            decision = agent.classify(_make_endpoint("GET", "/admin/users", "adminListUsers"))
        assert decision.target == MigrationTarget.SPLIT

    def test_classify_deprecate(self):
        agent = LLMArchitecturePlannerAgent()
        mock_resp = _mock_ollama_response("deprecate_or_merge", 0.65)
        with patch("httpx.post", return_value=mock_resp):
            decision = agent.classify(_make_endpoint("GET", "/v1/old", "oldEndpoint"))
        assert decision.target == MigrationTarget.DEPRECATE

    def test_fallback_on_connection_error(self):
        """If Ollama is not running, should fall back silently."""
        import httpx
        agent = LLMArchitecturePlannerAgent()
        with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
            decision = agent.classify(_make_endpoint())
        # Deterministic fallback: POST /users → GRPC
        assert decision.target == MigrationTarget.GRPC
        assert "fallback" in decision.rationale

    def test_fallback_on_timeout(self):
        import httpx
        agent = LLMArchitecturePlannerAgent()
        with patch("httpx.post", side_effect=httpx.TimeoutException("timeout")):
            decision = agent.classify(_make_endpoint())
        assert decision.target in MigrationTarget.__members__.values()
        assert "fallback" in decision.rationale

    def test_fallback_on_malformed_json(self):
        """Non-JSON response should trigger deterministic fallback."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"message": {"content": "I cannot classify this."}}
        mock_resp.raise_for_status.return_value = None
        agent = LLMArchitecturePlannerAgent()
        with patch("httpx.post", return_value=mock_resp):
            decision = agent.classify(_make_endpoint())
        assert "fallback" in decision.rationale

    def test_fallback_on_empty_content(self):
        """Empty message content triggers fallback."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"message": {"content": ""}}
        mock_resp.raise_for_status.return_value = None
        agent = LLMArchitecturePlannerAgent()
        with patch("httpx.post", return_value=mock_resp):
            decision = agent.classify(_make_endpoint())
        assert "fallback" in decision.rationale

    def test_confidence_clamped_above_1(self):
        """LLM might hallucinate confidence > 1.0 — must be clamped."""
        mock_resp = _mock_ollama_response("migrate_grpc", 1.5)
        agent = LLMArchitecturePlannerAgent()
        with patch("httpx.post", return_value=mock_resp):
            decision = agent.classify(_make_endpoint())
        assert decision.confidence <= 1.0

    def test_confidence_clamped_below_0(self):
        """Negative confidence must be clamped to 0.0."""
        mock_resp = _mock_ollama_response("migrate_grpc", -0.5)
        agent = LLMArchitecturePlannerAgent()
        with patch("httpx.post", return_value=mock_resp):
            decision = agent.classify(_make_endpoint())
        assert decision.confidence >= 0.0

    def test_json_wrapped_in_markdown_fences(self):
        """LLM sometimes wraps JSON in ```json ... ``` — should still parse."""
        inner = json.dumps({"target": "migrate_grpc", "confidence": 0.85, "rationale": "good."})
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"message": {"content": f"```json\n{inner}\n```"}}
        mock_resp.raise_for_status.return_value = None
        agent = LLMArchitecturePlannerAgent()
        with patch("httpx.post", return_value=mock_resp):
            decision = agent.classify(_make_endpoint())
        assert decision.target == MigrationTarget.GRPC

    def test_target_alias_grpc_string(self):
        """LLM returns 'gRPC' instead of 'migrate_grpc' — should normalise."""
        mock_resp = _mock_ollama_response("gRPC", 0.88)
        agent = LLMArchitecturePlannerAgent()
        with patch("httpx.post", return_value=mock_resp):
            decision = agent.classify(_make_endpoint())
        assert decision.target == MigrationTarget.GRPC

    def test_payload_uses_format_json(self):
        """Ensure format='json' is in the Ollama request payload."""
        captured = {}
        mock_resp = _mock_ollama_response("migrate_grpc")

        def capture_post(url, json=None, **kwargs):
            captured["payload"] = json
            return mock_resp

        agent = LLMArchitecturePlannerAgent()
        with patch("httpx.post", side_effect=capture_post):
            agent.classify(_make_endpoint())

        assert captured["payload"]["format"] == "json"
        assert captured["payload"]["stream"] is False
        assert len(captured["payload"]["messages"]) == 2
        assert captured["payload"]["messages"][0]["role"] == "system"
        assert captured["payload"]["messages"][1]["role"] == "user"

    def test_uses_correct_model(self):
        """The model specified in the constructor must be sent to Ollama."""
        captured = {}
        mock_resp = _mock_ollama_response("migrate_grpc")

        def capture_post(url, json=None, **kwargs):
            captured["model"] = json["model"]
            return mock_resp

        agent = LLMArchitecturePlannerAgent(model="mistral")
        with patch("httpx.post", side_effect=capture_post):
            agent.classify(_make_endpoint())

        assert captured["model"] == "mistral"


# ── ArchitecturePlannerAgent with use_llm=True ────────────────────────────────

class TestArchitecturePlannerAgentLLMMode:
    SAMPLE_OPENAPI = str(Path(__file__).parent.parent / "testopenapi.yaml")

    def _make_inventory(self):
        from agents.scanner.agent import ScannerAgent
        return ScannerAgent().scan(self.SAMPLE_OPENAPI)

    def test_plan_returns_migration_plan(self):
        mock_resp = _mock_ollama_response("migrate_grpc", 0.90)
        planner = ArchitecturePlannerAgent(use_llm=True, model="llama3.2")
        with patch("httpx.post", return_value=mock_resp):
            plan = planner.plan(self._make_inventory())
        assert plan.service_name == "Student API"
        assert len(plan.recommendations) > 0

    def test_plan_uses_llm_rationale(self):
        mock_resp = _mock_ollama_response("migrate_grpc", 0.91, "LLM says strongly typed DTOs.")
        planner = ArchitecturePlannerAgent(use_llm=True)
        with patch("httpx.post", return_value=mock_resp):
            plan = planner.plan(self._make_inventory())
        # LLM rationale should appear in at least one recommendation
        rationales = [r.rationale for r in plan.recommendations]
        assert any("LLM says" in r for r in rationales)

    def test_plan_llm_confidence_used(self):
        mock_resp = _mock_ollama_response("migrate_grpc", 0.77)
        planner = ArchitecturePlannerAgent(use_llm=True)
        with patch("httpx.post", return_value=mock_resp):
            plan = planner.plan(self._make_inventory())
        assert all(r.confidence == pytest.approx(0.77) for r in plan.recommendations)

    def test_plan_fallback_when_ollama_down(self):
        """Even with use_llm=True, if Ollama is down the plan should complete."""
        import httpx
        planner = ArchitecturePlannerAgent(use_llm=True)
        with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
            plan = planner.plan(self._make_inventory())
        assert len(plan.recommendations) > 0
        assert all("fallback" in r.rationale for r in plan.recommendations)

    def test_deterministic_mode_unchanged(self):
        """use_llm=False (default) must never call httpx.post."""
        planner = ArchitecturePlannerAgent(use_llm=False)
        with patch("httpx.post") as mock_post:
            plan = planner.plan(self._make_inventory())
        mock_post.assert_not_called()
        assert len(plan.recommendations) > 0

    def test_env_var_enables_llm(self, monkeypatch):
        """MIGRATION_USE_LLM=true env var should enable LLM mode."""
        monkeypatch.setenv("MIGRATION_USE_LLM", "true")
        planner = ArchitecturePlannerAgent()
        assert planner._use_llm is True

    def test_env_var_disabled_by_default(self, monkeypatch):
        """Without env var, LLM mode should be off."""
        monkeypatch.delenv("MIGRATION_USE_LLM", raising=False)
        planner = ArchitecturePlannerAgent()
        assert planner._use_llm is False

    def test_readiness_score_in_range(self):
        mock_resp = _mock_ollama_response("migrate_grpc", 0.88)
        planner = ArchitecturePlannerAgent(use_llm=True)
        with patch("httpx.post", return_value=mock_resp):
            plan = planner.plan(self._make_inventory())
        assert 0 <= plan.readiness_score <= 100
