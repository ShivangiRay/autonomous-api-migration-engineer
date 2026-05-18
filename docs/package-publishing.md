# Package Publishing

The project is configured as a Python package named `autonomous-api-migration-engineer`.

## Build Locally

```bash
python -m pip install build twine
python -m build
twine check dist/*
```

Expected artifacts:

```text
dist/autonomous_api_migration_engineer-0.1.1-py3-none-any.whl
dist/autonomous_api_migration_engineer-0.1.1.tar.gz
```

## Publish With A PyPI Token

Create a PyPI API token, then run:

```bash
TWINE_USERNAME=__token__ TWINE_PASSWORD=<your-pypi-token> twine upload dist/*
```

## Publish With GitHub Trusted Publishing

1. Create the project on PyPI.
2. In PyPI, configure a trusted publisher for:
   - owner: `ShivangiRay`
   - repository: `autonomous-api-migration-engineer`
   - workflow: `publish.yml`
   - environment: leave empty unless you add one later
3. Create a GitHub release or manually run **Publish Python Package** from Actions.

## Use After Publishing

```bash
pip install autonomous-api-migration-engineer
```

```bash
migration-engineer analyze --openapi ./openapi.yaml --output-dir ./migration-artifacts
```

```python
from autonomous_api_migration_engineer import run_migration

result = run_migration("openapi.yaml", "migration-artifacts")
print(result["plan"].readiness_score)
```

