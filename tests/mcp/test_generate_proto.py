"""
Tests for the generate_proto MCP tool.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from mcp.tools.generate_proto import generate_proto

SAMPLE_OPENAPI_PATH = str(Path(__file__).parent.parent.parent / "testopenapi.yaml")

INLINE_OPENAPI = textwrap.dedent("""
    openapi: 3.0.3
    info:
      title: Payment Service
      version: 1.0.0
    paths:
      /payments:
        post:
          summary: Create a payment
          operationId: createPayment
          requestBody:
            content:
              application/json:
                schema:
                  type: object
                  properties:
                    amount:
                      type: number
                    currency:
                      type: string
          responses:
            "201":
              description: Payment created
      /payments/{id}:
        get:
          summary: Get payment
          operationId: getPayment
          responses:
            "200":
              description: Payment details
""")


class TestGenerateProto:
    def test_full_service_mode(self):
        result = generate_proto(openapi_path=SAMPLE_OPENAPI_PATH)
        assert result["mode"] == "full_service"
        assert 'syntax = "proto3"' in result["proto_content"]
        assert result["service_name"] == "Student API"

    def test_full_service_contains_service_block(self):
        result = generate_proto(openapi_content=INLINE_OPENAPI)
        assert "service " in result["proto_content"]
        assert "{" in result["proto_content"]

    def test_single_endpoint_mode(self):
        result = generate_proto(
            openapi_content=INLINE_OPENAPI,
            endpoint_id="POST /payments",
        )
        assert result["mode"] == "single_endpoint"
        assert result["rpc_count"] == 1
        assert "CreatePayment" in result["proto_content"]

    def test_single_endpoint_request_fields(self):
        result = generate_proto(
            openapi_content=INLINE_OPENAPI,
            endpoint_id="POST /payments",
        )
        proto = result["proto_content"]
        assert "amount" in proto or "currency" in proto  # fields from schema

    def test_header_template_included(self):
        result = generate_proto(openapi_content=INLINE_OPENAPI, include_header_template=True)
        assert "header_template" in result
        assert "proto3" in result["header_template"]

    def test_header_template_excluded(self):
        result = generate_proto(openapi_content=INLINE_OPENAPI, include_header_template=False)
        assert "header_template" not in result

    def test_output_written_to_file(self, tmp_path):
        out = str(tmp_path / "test.proto")
        result = generate_proto(openapi_content=INLINE_OPENAPI, output_path=out)
        assert result["output_path"] == out
        content = Path(out).read_text()
        assert 'syntax = "proto3"' in content

    def test_invalid_endpoint_id_raises(self):
        with pytest.raises(ValueError, match="not found"):
            generate_proto(openapi_content=INLINE_OPENAPI, endpoint_id="PATCH /nonexistent")

    def test_no_spec_raises(self):
        with pytest.raises(ValueError, match="Provide either"):
            generate_proto()

    def test_rpc_count_full_service(self):
        result = generate_proto(openapi_content=INLINE_OPENAPI)
        # rpc_count tracks gRPC-recommended endpoints; must be >= 0
        assert isinstance(result["rpc_count"], int)
        assert result["rpc_count"] >= 0
