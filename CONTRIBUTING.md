# Contributing

Thanks for helping improve Autonomous API Migration Engineer.

## Development Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

For the dashboard:

```bash
cd apps/web-dashboard
npm install
npm run dev
```

## Repository Conventions

- Use Python-importable package names with underscores, such as `api_orchestrator` and `contract_generator`.
- Keep generated local artifacts under `build/`.
- Do not commit `.venv`, `node_modules`, `dist`, `.pytest_cache`, or personal sample files.
- Generated contracts must remain reviewable proposals until explicitly approved.
- Add tests when changing parser behavior, planner rules, proposal flow, or implementation generation.

## Pull Request Checklist

- Run `pytest`.
- Run `npm run build` in `apps/web-dashboard`.
- Update README/docs when changing user-facing workflow.
- Keep recommendations explainable with evidence, rationale, confidence, and compatibility notes.

