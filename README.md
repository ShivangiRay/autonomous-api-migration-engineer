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

Generated outputs include:

- `endpoint-inventory.json`
- `migration-plan.json`
- `contracts/user_service.proto`
- `events/user-events.asyncapi.json`
- `compatibility-report.json`
- `executive-report.md`
- `adr/0001-contract-migration-strategy.md`

## Demo Login

- Email: `demo@example.com`
- Password: `demo-password`
