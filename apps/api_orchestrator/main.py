from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from libs.common.workflow import MigrationWorkflow


app = FastAPI(title="Autonomous API Migration Engineer")


class AnalyzeRequest(BaseModel):
    openapi_path: str
    output_dir: str = "build/artifacts"


class ManualSpecRequest(BaseModel):
    service_name: str
    openapi_json: dict
    output_dir: str = "build/artifacts"


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/runs/analyze")
def analyze(request: AnalyzeRequest) -> dict:
    path = Path(request.openapi_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="OpenAPI file not found")
    result = MigrationWorkflow().run(path, request.output_dir)
    return {
        "service": result["inventory"].service_name,
        "readinessScore": result["plan"].readiness_score,
        "compatibilityScore": result["compatibility"].score,
        "reportPath": result["report_path"],
        "artifactCount": len(result["artifacts"]),
    }


@app.post("/runs/analyze-manual")
def analyze_manual(request: ManualSpecRequest) -> dict:
    with TemporaryDirectory() as tmp:
        spec = Path(tmp) / "manual-openapi.json"
        spec.write_text(__import__("json").dumps(request.openapi_json))
        result = MigrationWorkflow().run(spec, request.output_dir)
    return {
        "service": request.service_name,
        "readinessScore": result["plan"].readiness_score,
        "compatibilityScore": result["compatibility"].score,
        "reportPath": result["report_path"],
    }

