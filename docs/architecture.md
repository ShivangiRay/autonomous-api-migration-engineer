# Architecture

## Product Intent

Autonomous API Migration Engineer analyzes a legacy REST service, builds a service inventory, proposes a phased migration plan, generates target contracts, verifies compatibility, and produces an evidence-backed report. It is a platform engineering product, not a chatbot: every output is traceable to scanned inputs and every generated artifact requires human approval before finalization.

## Assumptions

- The bootstrap focuses on OpenAPI v3 JSON/YAML and deterministic source-code heuristics.
- The first demo domain is user management.
- LangGraph-compatible orchestration is represented as an explicit workflow graph class to avoid external service dependencies.
- PostgreSQL stores runs, artifacts, approvals, decisions, and audit events in production; the bootstrap uses JSON artifact persistence for local tests.

## System Components

- `apps/api_orchestrator`: FastAPI endpoints for upload/analyze, run status, artifacts, approvals, and report retrieval.
- `apps/web-dashboard`: React console with service overview, endpoint catalog, graph, diffs, risks, artifacts, approval queue, and report views.
- `agents/scanner`: parses OpenAPI and code hints into a service inventory.
- `agents/planner`: classifies endpoints and creates phased migration recommendations.
- `agents/contract_generator`: emits protoc-compatible `.proto` and AsyncAPI/JSON Schema event contracts.
- `agents/verifier`: validates contracts, compares REST shapes, and scores compatibility risk.
- `agents/reporter`: writes Markdown reports and ADRs with evidence.
- `libs/parsers`: reusable OpenAPI and source parsing.
- `libs/contracts`: protobuf/event rendering and compatibility helpers.
- `libs/common`: models, workflow graph, artifact storage, audit trail, demo entrypoint.

## Workflow

1. Scanner Agent builds `endpoint-inventory.json`.
2. Planner Agent creates `migration-plan.json` with phase gates.
3. Contract Generation Agent writes proposed contracts into a draft artifact namespace.
4. Verification Agent computes endpoint compatibility scores and risk flags.
5. Reporting Agent writes executive report, diagrams, ADRs, and validation summary.
6. Human approval finalizes or rejects generated contracts.
7. A rerun can start from edited inventory, plan, or contract proposals.

## Data Model

- `analysis_run`: id, service name, status, readiness score, created_at.
- `endpoint`: method, path, operation_id, domain, request_schema, response_schema, auth, pagination, idempotency.
- `recommendation`: endpoint_id, target, rationale, confidence, impacted_dependencies, rollout_phase.
- `artifact`: run_id, type, path, checksum, provenance, approval_status.
- `audit_event`: actor, action, input_refs, output_refs, timestamp.
- `approval`: artifact_id, reviewer, decision, comment.

## Implementation Phases

1. Analysis only: parse specs and source hints.
2. Contract proposal: generate proto and event schema drafts.
3. Validation: compatibility scoring, lint-style checks, and regression cases.
4. Migration report: evidence, rollout plan, ADRs, and rollback strategy.

## Key Risks

- Incomplete source parsing can miss runtime behavior; reports show confidence and evidence gaps.
- REST to event conversion can overfit CRUD naming; planner requires explicit rationale and dependencies.
- Proto field evolution needs stable numbering; generated contracts reserve provenance metadata.
- Human approval must remain mandatory before contract finalization.
