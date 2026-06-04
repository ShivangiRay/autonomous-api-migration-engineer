"""
Tests for MCP resources — list_resources and read_resource.
"""
from __future__ import annotations

import pytest

from mcp.resources import list_resources, read_resource

EXPECTED_URIS = {
    "migration://templates/proto_header",
    "migration://templates/error_mapping",
    "migration://templates/interceptors",
    "migration://templates/grpc_client",
}


class TestListResources:
    def test_returns_all_four_resources(self):
        resources = list_resources()
        uris = {r["uri"] for r in resources}
        assert uris == EXPECTED_URIS

    def test_each_resource_has_required_fields(self):
        for resource in list_resources():
            assert "uri" in resource
            assert "name" in resource
            assert "description" in resource
            assert "mimeType" in resource

    def test_mime_types(self):
        by_uri = {r["uri"]: r for r in list_resources()}
        assert by_uri["migration://templates/proto_header"]["mimeType"] == "text/plain"
        assert by_uri["migration://templates/error_mapping"]["mimeType"] == "text/markdown"
        assert by_uri["migration://templates/interceptors"]["mimeType"] == "text/x-python"
        assert by_uri["migration://templates/grpc_client"]["mimeType"] == "text/x-python"


class TestReadResource:
    def test_proto_header_content(self):
        result = read_resource("migration://templates/proto_header")
        assert result["mimeType"] == "text/plain"
        assert 'syntax = "proto3"' in result["text"]
        assert "<org>" in result["text"]

    def test_error_mapping_content(self):
        result = read_resource("migration://templates/error_mapping")
        assert "NOT_FOUND" in result["text"]
        assert "404" in result["text"]
        assert "UNAUTHENTICATED" in result["text"]
        assert "401" in result["text"]

    def test_interceptors_content(self):
        result = read_resource("migration://templates/interceptors")
        assert "LoggingServerInterceptor" in result["text"]
        assert "AuthServerInterceptor" in result["text"]
        assert "RetryClientInterceptor" in result["text"]
        assert "build_server" in result["text"]

    def test_grpc_client_content(self):
        result = read_resource("migration://templates/grpc_client")
        assert "<ServiceName>GrpcClient" in result["text"]
        assert "use_tls" in result["text"]
        assert "grpc_tools.protoc" in result["text"]

    def test_read_resource_returns_uri(self):
        result = read_resource("migration://templates/proto_header")
        assert result["uri"] == "migration://templates/proto_header"

    def test_unknown_uri_raises(self):
        with pytest.raises(ValueError, match="Unknown resource URI"):
            read_resource("migration://templates/nonexistent")

    def test_all_resources_readable(self):
        for uri in EXPECTED_URIS:
            result = read_resource(uri)
            assert result["text"], f"Resource {uri} returned empty content"
