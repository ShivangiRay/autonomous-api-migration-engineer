from __future__ import annotations

import json
from pathlib import Path

from libs.common.models import GrpcMigrationProposal, ProposalComment
from libs.contracts.protobuf import apply_proto_comment


class ApprovalAgent:
    name = "approval"

    def add_comment(self, proposal_path: str | Path, body: str, author: str = "developer") -> GrpcMigrationProposal:
        proposal = self._load(proposal_path)
        proposal.comments.append(ProposalComment(author=author, body=body))
        proposal.status = "changes_requested"
        self._save(proposal_path, proposal)
        return proposal

    def resolve_comments(self, proposal_path: str | Path) -> GrpcMigrationProposal:
        proposal = self._load(proposal_path)
        for comment in proposal.comments:
            if not comment.resolved:
                proposal.proposed_proto = apply_proto_comment(proposal.proposed_proto, comment.body)
                comment.resolved = True
        proposal.status = "needs_review"
        self._save(proposal_path, proposal)
        return proposal

    def approve(self, proposal_path: str | Path) -> GrpcMigrationProposal:
        proposal = self._load(proposal_path)
        unresolved = [comment for comment in proposal.comments if not comment.resolved]
        if unresolved:
            raise ValueError("Cannot approve while comments are unresolved.")
        proposal.status = "approved"
        self._save(proposal_path, proposal)
        return proposal

    def _load(self, proposal_path: str | Path) -> GrpcMigrationProposal:
        return GrpcMigrationProposal(**json.loads(Path(proposal_path).read_text()))

    def _save(self, proposal_path: str | Path, proposal: GrpcMigrationProposal) -> None:
        Path(proposal_path).write_text(proposal.model_dump_json(indent=2))

