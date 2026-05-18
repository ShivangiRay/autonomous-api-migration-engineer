# Changelog

## 0.1.1

- Removed duplicate hyphenated compatibility directories in favor of Python-importable underscore packages.
- Updated README and architecture docs to reference `apps/api_orchestrator` and `agents/contract_generator`.
- Added structural tests to prevent duplicate package naming from returning.
- Added one repo-accurate CI workflow for Python tests and dashboard production builds.
- Removed auto-generated CI workflows that expected missing files or incomplete dependencies.
- Expanded Python dependencies for protobuf generation, multipart uploads, async tests, formatting, and linting.

## 0.1.0

- Bootstrap release with OpenAPI parsing, migration planning, gRPC/event proposals, approval flow, local RAG-style memory, dashboard UI, and tests.
