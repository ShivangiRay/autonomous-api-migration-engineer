# Changelog

## 0.1.1

- Removed duplicate hyphenated compatibility directories in favor of Python-importable underscore packages.
- Updated README and architecture docs to reference `apps/api_orchestrator` and `agents/contract_generator`.
- Added structural tests to prevent duplicate package naming from returning.
- Added one repo-accurate CI workflow for Python tests and dashboard production builds.
- Removed auto-generated CI workflows that expected missing files or incomplete dependencies.
- Added PyPI-ready package metadata, MIT license, and the public `autonomous_api_migration_engineer` integration namespace.
- Added `--openapi` as a CLI alias for easier package usage from external projects.
- Added package publishing documentation and a GitHub Actions workflow for PyPI releases.
- Expanded Python dependencies for protobuf generation, multipart uploads, async tests, formatting, and linting.

## 0.1.0

- Bootstrap release with OpenAPI parsing, migration planning, gRPC/event proposals, approval flow, local RAG-style memory, dashboard UI, and tests.
