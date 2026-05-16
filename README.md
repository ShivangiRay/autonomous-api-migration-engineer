# Autonomous API Migration Engineer

AI-assisted platform for analyzing legacy REST services and proposing migrations to gRPC, event-driven architecture, and improved contracts.

This bootstrap is intentionally deterministic: it uses graph-style local agents, sample OpenAPI input, generated protobuf/event schemas, compatibility checks, reports, and tests without requiring paid external APIs.

## What Is Included

- FastAPI orchestration API in `apps/api-orchestrator`
- React dashboard scaffold in `apps/web-dashboard`
- Multi-agent workflow across scanner, planner, contract generator, verifier, and reporter agents
- OpenAPI v3 parser and sample legacy user-management service
- Generated artifacts with provenance metadata
- Human approval queue model before finalizing generated contracts
- Docker Compose for API, web, PostgreSQL, and Redis
- Unit/integration tests for the happy path

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
uvicorn apps.api-orchestrator.main:app --reload --port 8000
```

Dashboard scaffold:

```bash
cd apps/web-dashboard
npm install
npm run dev
```

Docker:

```bash
docker compose -f infra/docker-compose.yml up --build
```

## Demo Workflow

Run the sample workflow:

```bash
python -m libs.common.demo examples/sample-openapi/user-management.openapi.json build/artifacts
```

Interactive migration proposal flow:

```bash
migration-engineer analyze
migration-engineer propose-grpc --endpoint "POST /users"
migration-engineer comment --proposal build/proposals/proposal-post-users.json --body "Add idempotency key and validation notes"
migration-engineer resolve-comments --proposal build/proposals/proposal-post-users.json
migration-engineer approve --proposal build/proposals/proposal-post-users.json
migration-engineer implement-grpc --proposal build/proposals/proposal-post-users.json
```

RAG-style local memory:

```bash
migration-engineer memory
migration-engineer propose-grpc --endpoint "POST /users"
```

The implementation step writes successful approved migrations into `build/memory/migration-memory.jsonl`. Future proposals retrieve similar local cases and include the retrieved cases plus learned adjustments in the proposal basis. This is not model fine-tuning; it is transparent retrieval over prior generated/reviewed artifacts.

Event transport proposal:

```bash
migration-engineer propose-event --endpoint "PATCH /users/{userId}"
```

The event proposal recommends Kafka when the endpoint looks like a durable domain event that benefits from replay, ordering, and fan-out. It recommends RabbitMQ when the endpoint looks more like command dispatch, task routing, or worker handoff.

Generated outputs include:

- `endpoint-inventory.json`
- `migration-plan.json`
- `contracts/user_service.proto`
- `events/user-events.asyncapi.json`
- `compatibility-report.json`
- `executive-report.md`
- `adr/0001-contract-migration-strategy.md`

Proposal outputs include the basis for the suggestion. The bootstrap does not train agents on private data; it uses deterministic rules over supplied OpenAPI/source evidence and records that basis in the proposal JSON.

## Demo Login

- Email: `demo@example.com`
- Password: `demo-password`
