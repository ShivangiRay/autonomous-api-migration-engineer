"""
Tests for the generate_grpc_client MCP tool.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp.tools.generate_grpc_client import generate_grpc_client

SAMPLE_PROTO = '''\
syntax = "proto3";

package migration.user_management.v1;

service UserManagementGrpc {
  rpc CreateUser (CreateUserRequest) returns (CreateUserResponse);
  rpc GetUser (GetUserRequest) returns (GetUserResponse);
  rpc DeleteUser (DeleteUserRequest) returns (DeleteUserResponse);
}

message CreateUserRequest {
  string email = 1;
  string name = 2;
}

message CreateUserResponse {
  string id = 1;
  string email = 2;
  string status = 3;
}

message GetUserRequest {
  string user_id = 1;
}

message GetUserResponse {
  string id = 1;
  string email = 2;
}

message DeleteUserRequest {
  string user_id = 1;
}

message DeleteUserResponse {
  string payload_json = 1;
}
'''


class TestGenerateGrpcClient:
    def test_generates_client_code(self):
        result = generate_grpc_client(proto_content=SAMPLE_PROTO)
        assert "client_code" in result
        assert "class UserManagementGrpcClient" in result["client_code"]

    def test_service_name_detected(self):
        result = generate_grpc_client(proto_content=SAMPLE_PROTO)
        assert result["service_name"] == "UserManagementGrpc"

    def test_rpc_methods_listed(self):
        result = generate_grpc_client(proto_content=SAMPLE_PROTO)
        methods = result["rpc_methods"]
        assert "create_user" in methods
        assert "get_user" in methods
        assert "delete_user" in methods

    def test_method_stubs_in_code(self):
        result = generate_grpc_client(proto_content=SAMPLE_PROTO)
        code = result["client_code"]
        assert "def create_user" in code
        assert "def get_user" in code
        assert "def delete_user" in code

    def test_field_params_in_method_signature(self):
        result = generate_grpc_client(proto_content=SAMPLE_PROTO)
        code = result["client_code"]
        # CreateUserRequest has email and name fields
        assert "email" in code
        assert "name" in code

    def test_tls_options_in_code(self):
        result = generate_grpc_client(proto_content=SAMPLE_PROTO)
        code = result["client_code"]
        assert "use_tls" in code
        assert "ssl_channel_credentials" in code

    def test_context_manager_in_code(self):
        result = generate_grpc_client(proto_content=SAMPLE_PROTO)
        code = result["client_code"]
        assert "__enter__" in code
        assert "__exit__" in code
        assert "close" in code

    def test_protoc_command_returned(self):
        result = generate_grpc_client(proto_content=SAMPLE_PROTO, module_name="user_service")
        assert "grpc_tools.protoc" in result["protoc_command"]
        assert "user_service.proto" in result["protoc_command"]

    def test_interceptors_included_by_default(self):
        result = generate_grpc_client(proto_content=SAMPLE_PROTO)
        assert "interceptors_template" in result
        assert "LoggingServerInterceptor" in result["interceptors_template"]

    def test_interceptors_excluded(self):
        result = generate_grpc_client(proto_content=SAMPLE_PROTO, include_interceptors=False)
        assert "interceptors_template" not in result

    def test_output_written_to_file(self, tmp_path):
        out = str(tmp_path / "grpc_client.py")
        result = generate_grpc_client(proto_content=SAMPLE_PROTO, output_path=out)
        assert result["output_path"] == out
        content = Path(out).read_text()
        assert "UserManagementGrpcClient" in content

    def test_from_proposal_path(self, tmp_path):
        proposal = {
            "id": "proposal-post-users",
            "endpoint_id": "POST /users",
            "status": "approved",
            "basis": {},
            "proposed_proto": SAMPLE_PROTO,
        }
        proposal_path = tmp_path / "proposal.json"
        proposal_path.write_text(json.dumps(proposal))
        result = generate_grpc_client(proposal_path=str(proposal_path))
        assert "client_code" in result
        assert "UserManagementGrpc" in result["service_name"]

    def test_no_input_raises(self):
        with pytest.raises(ValueError, match="Provide either"):
            generate_grpc_client()

    def test_empty_proto_raises(self):
        with pytest.raises(ValueError, match="No rpc methods found"):
            generate_grpc_client(proto_content='syntax = "proto3";')
