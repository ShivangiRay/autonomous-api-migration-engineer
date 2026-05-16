from pathlib import Path

from agents.approval.agent import ApprovalAgent
from agents.implementation.agent import ImplementationAgent
from libs.common.proposals import propose_grpc


FIXTURE = Path("examples/sample-openapi/user-management.openapi.json")


def test_proposal_comment_approval_and_implementation(tmp_path: Path) -> None:
    proposal_path = propose_grpc(FIXTURE, "POST /users", tmp_path / "proposals")
    proposal = ApprovalAgent().add_comment(proposal_path, "Add idempotency key and validation notes")
    assert proposal.status == "changes_requested"

    proposal = ApprovalAgent().resolve_comments(proposal_path)
    assert "idempotency_key" in proposal.proposed_proto
    assert all(comment.resolved for comment in proposal.comments)

    proposal = ApprovalAgent().approve(proposal_path)
    assert proposal.status == "approved"

    files = ImplementationAgent().implement(proposal_path, tmp_path / "implementation")
    assert len(files) == 5
    assert (tmp_path / "implementation" / "generated_grpc" / "server" / "user_service_impl.py").exists()
    assert (tmp_path / "implementation" / "tests" / "test_create_user_grpc_mapping.py").exists()
