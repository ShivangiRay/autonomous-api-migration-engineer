from __future__ import annotations

import json
from pathlib import Path

from libs.common.models import GrpcMigrationProposal


class ImplementationAgent:
    name = "implementation"

    def implement(self, proposal_path: str | Path, output_dir: str | Path) -> list[Path]:
        proposal = GrpcMigrationProposal(**json.loads(Path(proposal_path).read_text()))
        if proposal.status != "approved":
            raise ValueError("Proposal must be approved before implementation.")

        root = Path(output_dir)
        package_dir = root / "generated_grpc"
        proto_dir = package_dir / "proto"
        service_dir = package_dir / "server"
        tests_dir = root / "tests"
        proto_dir.mkdir(parents=True, exist_ok=True)
        service_dir.mkdir(parents=True, exist_ok=True)
        tests_dir.mkdir(parents=True, exist_ok=True)

        package_init = package_dir / "__init__.py"
        server_init = service_dir / "__init__.py"
        proto_path = proto_dir / "user_service.proto"
        service_path = service_dir / "user_service_impl.py"
        test_path = tests_dir / "test_create_user_grpc_mapping.py"

        self._write_once(package_init, "")
        self._write_once(server_init, "")
        self._write_once(proto_path, proposal.proposed_proto)
        self._write_once(service_path, self._service_impl())
        self._write_once(test_path, self._test_impl())

        proposal.status = "implemented"
        proposal.generated_files = [str(package_init), str(server_init), str(proto_path), str(service_path), str(test_path)]
        Path(proposal_path).write_text(proposal.model_dump_json(indent=2))
        return [package_init, server_init, proto_path, service_path, test_path]

    def _write_once(self, path: Path, content: str) -> None:
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite existing generated file: {path}")
        path.write_text(content)

    def _service_impl(self) -> str:
        return '''from __future__ import annotations


class UserApplicationService:
    def create_user(self, email: str) -> dict:
        return {"id": "usr_002", "email": email, "status": "active"}


class UserServiceGrpc:
    def __init__(self, app_service: UserApplicationService | None = None) -> None:
        self.app_service = app_service or UserApplicationService()

    def CreateUser(self, request, context=None):
        user = self.app_service.create_user(email=request.email)
        return {
            "user": {
                "id": user["id"],
                "email": user["email"],
                "status": user["status"],
            }
        }
'''

    def _test_impl(self) -> str:
        return '''from generated_grpc.server.user_service_impl import UserServiceGrpc


class Request:
    email = "demo@example.com"


def test_create_user_grpc_mapping() -> None:
    response = UserServiceGrpc().CreateUser(Request())
    assert response["user"]["email"] == "demo@example.com"
    assert response["user"]["status"] == "active"
'''
