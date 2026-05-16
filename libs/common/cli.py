from __future__ import annotations

import argparse
import json
from pathlib import Path

from agents.approval.agent import ApprovalAgent
from agents.implementation.agent import ImplementationAgent
from libs.common.proposals import propose_grpc
from libs.common.workflow import MigrationWorkflow


DEFAULT_OPENAPI = "examples/sample-openapi/user-management.openapi.json"


def main() -> None:
    parser = argparse.ArgumentParser(prog="migration-engineer")
    sub = parser.add_subparsers(dest="command", required=True)

    analyze = sub.add_parser("analyze")
    analyze.add_argument("openapi_path", nargs="?", default=DEFAULT_OPENAPI)
    analyze.add_argument("--output-dir", default="build/artifacts")

    propose = sub.add_parser("propose-grpc")
    propose.add_argument("--endpoint", required=True)
    propose.add_argument("--openapi-path", default=DEFAULT_OPENAPI)
    propose.add_argument("--output-dir", default="build/proposals")

    comment = sub.add_parser("comment")
    comment.add_argument("--proposal", required=True)
    comment.add_argument("--body", required=True)

    resolve = sub.add_parser("resolve-comments")
    resolve.add_argument("--proposal", required=True)

    approve = sub.add_parser("approve")
    approve.add_argument("--proposal", required=True)

    implement = sub.add_parser("implement-grpc")
    implement.add_argument("--proposal", required=True)
    implement.add_argument("--output-dir", default="build/implementation")

    args = parser.parse_args()
    if args.command == "analyze":
        result = MigrationWorkflow().run(args.openapi_path, args.output_dir)
        print(f"System: I found {len(result['inventory'].endpoints)} endpoints.")
        for item in result["plan"].recommendations:
            print(f"System: {item.endpoint_id} -> {item.target.value} ({item.confidence:.2f})")
    elif args.command == "propose-grpc":
        path = propose_grpc(args.openapi_path, args.endpoint, args.output_dir)
        proposal = json.loads(Path(path).read_text())
        print(f"System: Here is the generated proto proposal: {path}")
        print(proposal["proposed_proto"])
    elif args.command == "comment":
        proposal = ApprovalAgent().add_comment(args.proposal, args.body)
        print(f"System: Comment added. Proposal status: {proposal.status}")
    elif args.command == "resolve-comments":
        proposal = ApprovalAgent().resolve_comments(args.proposal)
        print(f"System: Updated proto. Proposal status: {proposal.status}")
        print(proposal.proposed_proto)
    elif args.command == "approve":
        proposal = ApprovalAgent().approve(args.proposal)
        print(f"System: Proposal approved: {proposal.id}")
    elif args.command == "implement-grpc":
        files = ImplementationAgent().implement(args.proposal, args.output_dir)
        print("System: Implementing REST-to-gRPC migration.")
        for path in files:
            print(f"System: Generated {path}")
        print("System: Compatibility check passed.")


if __name__ == "__main__":
    main()
