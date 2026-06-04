"""
Tests for the migrate_code MCP tool.
"""
from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from mcp.tools.migrate_code import migrate_code

# A spec where POST /users is classified as gRPC (no 'event'/'status' keyword,
# uses POST → matches GRPC in the planner classifier).
GRPC_SPEC = textwrap.dedent("""
    openapi: 3.0.3
    info:
      title: User Management API
      version: 1.0.0
    paths:
      /users:
        post:
          summary: Create a user
          operationId: createUser
          requestBody:
            content:
              application/json:
                schema:
                  type: object
                  properties:
                    email:
                      type: string
          responses:
            "201":
              description: User created
              content:
                application/json:
                  schema:
                    $ref: "#/components/schemas/User"
""")

# A spec where the endpoint is classified as REST by the planner.
# The planner rule: GET + "users" in path + no path param → keep_rest.
REST_SPEC = textwrap.dedent("""
    openapi: 3.0.3
    info:
      title: User Catalog
      version: 1.0.0
    paths:
      /users:
        get:
          summary: List all users
          operationId: listUsers
          responses:
            "200":
              description: Users
""")


class TestMigrateCode:
    def test_full_pipeline_grpc_endpoint(self, tmp_path):
        result = migrate_code(
            endpoint_id="POST /users",
            openapi_content=GRPC_SPEC,
            output_dir=str(tmp_path / "migration"),
        )
        assert result["skipped"] is False
        assert result["endpoint_id"] == "POST /users"
        assert result["migration_target"] == "migrate_grpc"
        assert "proto_content" in result
        assert 'syntax = "proto3"' in result["proto_content"]

    def test_generated_files_exist(self, tmp_path):
        result = migrate_code(
            endpoint_id="POST /users",
            openapi_content=GRPC_SPEC,
            output_dir=str(tmp_path / "migration"),
        )
        for file_path in result["generated_files"]:
            assert Path(file_path).exists(), f"Expected generated file: {file_path}"

    def test_file_contents_returned(self, tmp_path):
        result = migrate_code(
            endpoint_id="POST /users",
            openapi_content=GRPC_SPEC,
            output_dir=str(tmp_path / "migration"),
        )
        assert isinstance(result["file_contents"], dict)
        assert len(result["file_contents"]) > 0

    def test_service_impl_in_generated_files(self, tmp_path):
        result = migrate_code(
            endpoint_id="POST /users",
            openapi_content=GRPC_SPEC,
            output_dir=str(tmp_path / "migration"),
        )
        impl_files = [f for f in result["generated_files"] if "impl" in f or ".proto" in f]
        assert len(impl_files) > 0

    def test_non_grpc_endpoint_skipped(self, tmp_path):
        result = migrate_code(
            endpoint_id="GET /users",
            openapi_content=REST_SPEC,
            output_dir=str(tmp_path / "migration"),
        )
        assert result["skipped"] is True
        assert "reason" in result
        assert "migrate_grpc" in result["reason"]

    def test_invalid_endpoint_raises(self, tmp_path):
        with pytest.raises(ValueError, match="not found"):
            migrate_code(
                endpoint_id="DELETE /nonexistent",
                openapi_content=GRPC_SPEC,
                output_dir=str(tmp_path / "migration"),
            )

    def test_no_spec_raises(self, tmp_path):
        with pytest.raises(ValueError, match="Provide either"):
            migrate_code(
                endpoint_id="POST /users",
                output_dir=str(tmp_path / "migration"),
            )

    def test_proposal_path_returned(self, tmp_path):
        result = migrate_code(
            endpoint_id="POST /users",
            openapi_content=GRPC_SPEC,
            output_dir=str(tmp_path / "migration"),
        )
        assert "proposal_path" in result
        assert Path(result["proposal_path"]).exists()

    def test_proposal_is_approved(self, tmp_path):
        result = migrate_code(
            endpoint_id="POST /users",
            openapi_content=GRPC_SPEC,
            output_dir=str(tmp_path / "migration"),
        )
        proposal = json.loads(Path(result["proposal_path"]).read_text())
        assert proposal["status"] == "implemented"

    def test_confidence_score_present(self, tmp_path):
        result = migrate_code(
            endpoint_id="POST /users",
            openapi_content=GRPC_SPEC,
            output_dir=str(tmp_path / "migration"),
        )
        assert 0.0 <= result["confidence"] <= 1.0
