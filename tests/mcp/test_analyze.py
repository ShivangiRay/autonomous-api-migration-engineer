"""
Tests for the analyze_rest_endpoint MCP tool.
"""
from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from mcp.tools.analyze import analyze_rest_endpoint

# ── Fixtures ──────────────────────────────────────────────────────────────────

SAMPLE_OPENAPI_PATH = str(Path(__file__).parent.parent.parent / "testopenapi.yaml")

INLINE_OPENAPI = textwrap.dedent("""
    openapi: 3.0.3
    info:
      title: Order Service
      version: 1.0.0
    paths:
      /orders:
        post:
          summary: Create an order
          operationId: createOrder
          requestBody:
            content:
              application/json:
                schema:
                  type: object
                  properties:
                    customer_id:
                      type: string
                    amount:
                      type: number
          responses:
            "201":
              description: Order created
              content:
                application/json:
                  schema:
                    $ref: "#/components/schemas/Order"
      /orders/{id}:
        get:
          summary: Get order by ID
          operationId: getOrderById
          responses:
            "200":
              description: Order details
""")


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestAnalyzeRestEndpoint:
    def test_analyze_from_file_path(self):
        result = analyze_rest_endpoint(openapi_path=SAMPLE_OPENAPI_PATH)
        assert "service_name" in result
        assert "endpoint_analyses" in result
        assert isinstance(result["endpoint_analyses"], list)
        assert len(result["endpoint_analyses"]) > 0

    def test_analyze_from_inline_content(self):
        result = analyze_rest_endpoint(openapi_content=INLINE_OPENAPI)
        assert result["service_name"] == "Order Service"
        assert result["total_endpoints"] == 2

    def test_summary_counts(self):
        result = analyze_rest_endpoint(openapi_content=INLINE_OPENAPI)
        summary = result["summary"]
        total = summary["grpc_candidates"] + summary["event_candidates"] + summary["keep_rest"] + summary["other"]
        assert total == result["total_endpoints"]

    def test_single_endpoint_filter(self):
        result = analyze_rest_endpoint(
            openapi_content=INLINE_OPENAPI,
            endpoint_id="POST /orders",
        )
        assert len(result["endpoint_analyses"]) == 1
        analysis = result["endpoint_analyses"][0]
        assert analysis["endpoint_id"] == "POST /orders"
        assert analysis["http_method"] == "POST"

    def test_endpoint_analysis_structure(self):
        result = analyze_rest_endpoint(openapi_content=INLINE_OPENAPI)
        analysis = result["endpoint_analyses"][0]
        assert "grpc_mapping" in analysis
        assert "rpc_pattern" in analysis
        assert "request_message" in analysis
        assert "response_message" in analysis
        assert "metadata" in analysis
        assert "confidence" in analysis["grpc_mapping"]

    def test_request_message_fields(self):
        result = analyze_rest_endpoint(
            openapi_content=INLINE_OPENAPI,
            endpoint_id="POST /orders",
        )
        analysis = result["endpoint_analyses"][0]
        req_fields = analysis["request_message"]["fields"]
        field_names = [f["name"] for f in req_fields]
        assert "customer_id" in field_names
        assert "amount" in field_names

    def test_invalid_endpoint_id_raises(self):
        with pytest.raises(ValueError, match="not found"):
            analyze_rest_endpoint(
                openapi_content=INLINE_OPENAPI,
                endpoint_id="DELETE /nonexistent",
            )

    def test_no_spec_raises(self):
        with pytest.raises(ValueError, match="Provide either"):
            analyze_rest_endpoint()

    def test_rollout_phases_present(self):
        result = analyze_rest_endpoint(openapi_content=INLINE_OPENAPI)
        assert "rollout_phases" in result
        phases = result["rollout_phases"]
        assert "phase_1_analysis_only" in phases

    def test_readiness_score_in_range(self):
        result = analyze_rest_endpoint(openapi_path=SAMPLE_OPENAPI_PATH)
        assert 0 <= result["readiness_score"] <= 100
