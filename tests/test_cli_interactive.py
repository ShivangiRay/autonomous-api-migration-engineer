from pathlib import Path

from libs.common.cli import _ask_to_proceed
from libs.common.models import MigrationTarget, Recommendation


FIXTURE = Path("examples/sample-openapi/user-management.openapi.json")


def test_interactive_analysis_generates_proposal_when_user_accepts(tmp_path: Path, monkeypatch) -> None:
    recommendations = [
        Recommendation(
            endpoint_id="POST /users",
            target=MigrationTarget.GRPC,
            phase=2,
            rationale="Typed create endpoint is a gRPC candidate.",
            confidence=0.86,
        )
    ]
    monkeypatch.setattr("builtins.input", lambda _: "yes")

    _ask_to_proceed(recommendations, str(FIXTURE), str(tmp_path))

    assert (tmp_path / "proposal-post-users.json").exists()


def test_interactive_analysis_skips_when_user_declines(tmp_path: Path, monkeypatch) -> None:
    recommendations = [
        Recommendation(
            endpoint_id="POST /users",
            target=MigrationTarget.GRPC,
            phase=2,
            rationale="Typed create endpoint is a gRPC candidate.",
            confidence=0.86,
        )
    ]
    monkeypatch.setattr("builtins.input", lambda _: "no")

    _ask_to_proceed(recommendations, str(FIXTURE), str(tmp_path))

    assert not (tmp_path / "proposal-post-users.json").exists()
