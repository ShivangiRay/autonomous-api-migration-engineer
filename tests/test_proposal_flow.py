from pathlib import Path

from agents.approval.agent import ApprovalAgent
from agents.implementation.agent import ImplementationAgent
from libs.common.memory import MigrationMemoryStore
from libs.common.models import MemoryCase
from libs.common.proposals import propose_event, propose_grpc


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


def test_grpc_proposal_retrieves_local_memory(tmp_path: Path) -> None:
    memory_path = tmp_path / "memory.jsonl"
    MigrationMemoryStore(memory_path).add(
        MemoryCase(
            id="memory-create-user",
            endpoint_id="POST /users",
            target="migrate_grpc",
            decision="implemented",
            rationale="Approved CreateUser migration with idempotency key.",
            tags=["grpc", "users", "create"],
            learned_adjustments=["Prefer idempotency_key for create-style RPCs."],
        )
    )

    proposal_path = propose_grpc(FIXTURE, "POST /users", tmp_path / "proposals", memory_path)
    proposal_text = proposal_path.read_text()
    assert "memory-create-user" in proposal_text
    assert "Prefer idempotency_key" in proposal_text


def test_event_proposal_recommends_kafka_for_status_event(tmp_path: Path) -> None:
    proposal_path = propose_event(FIXTURE, "PATCH /users/{userId}", tmp_path / "events")
    proposal_text = proposal_path.read_text()
    assert '"transport": "kafka"' in proposal_text
    assert "durable domain event" in proposal_text
