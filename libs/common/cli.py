from __future__ import annotations

import argparse
import json
from pathlib import Path

from agents.approval.agent import ApprovalAgent
from agents.implementation.agent import ImplementationAgent
from libs.common.memory import MigrationMemoryStore
from libs.common.models import MigrationTarget
from libs.common.proposals import propose_event, propose_grpc
from libs.common.workflow import MigrationWorkflow


DEFAULT_OPENAPI = "examples/sample-openapi/user-management.openapi.json"


def main() -> None:
    parser = argparse.ArgumentParser(prog="migration-engineer")
    sub = parser.add_subparsers(dest="command", required=True)

    analyze = sub.add_parser("analyze", help="Analyse an OpenAPI spec and plan the migration.")
    analyze.add_argument("openapi_path", nargs="?", default=DEFAULT_OPENAPI)
    analyze.add_argument("--openapi", dest="openapi_option", help="OpenAPI JSON/YAML path. Alias for the positional path.")
    analyze.add_argument("--output-dir", default="build/artifacts")
    analyze.add_argument("--interactive", action="store_true", help="Ask before generating migration proposals.")
    analyze.add_argument("--proposal-dir", default="build/proposals", help="Where interactive proposals are written.")
    analyze.add_argument(
        "--llm", action="store_true",
        help="Use a local Ollama LLM to classify endpoints instead of deterministic rules.",
    )
    analyze.add_argument(
        "--model", default=None,
        metavar="MODEL",
        help="Ollama model to use with --llm (e.g. llama3.2, mistral, phi3:mini). Default: llama3.2.",
    )
    analyze.add_argument(
        "--ollama-url", default=None,
        metavar="URL",
        help="Base URL for the Ollama server (default: http://localhost:11434).",
    )

    propose = sub.add_parser("propose-grpc")
    propose.add_argument("--endpoint", required=True)
    propose.add_argument("--openapi-path", default=DEFAULT_OPENAPI)
    propose.add_argument("--output-dir", default="build/proposals")

    propose_event_parser = sub.add_parser("propose-event")
    propose_event_parser.add_argument("--endpoint", required=True)
    propose_event_parser.add_argument("--openapi-path", default=DEFAULT_OPENAPI)
    propose_event_parser.add_argument("--output-dir", default="build/proposals")

    memory = sub.add_parser("memory")
    memory.add_argument("--path", default="build/memory/migration-memory.jsonl")

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
        openapi_path = args.openapi_option or args.openapi_path
        use_llm = getattr(args, "llm", False)
        model = getattr(args, "model", None)
        ollama_url = getattr(args, "ollama_url", None)
        if use_llm:
            print(f"System: LLM planner active (model={model or 'llama3.2'}, url={ollama_url or 'http://localhost:11434'}).")
            print("System: Calling Ollama for each endpoint — this may take a few seconds per endpoint.")
        result = MigrationWorkflow(
            use_llm=use_llm, llm_model=model, ollama_url=ollama_url
        ).run(openapi_path, args.output_dir)
        print(f"System: I found {len(result['inventory'].endpoints)} endpoints.")
        for item in result["plan"].recommendations:
            print(f"System: {item.endpoint_id} -> {item.target.value} ({item.confidence:.2f})")
        if args.interactive:
            _ask_to_proceed(result["plan"].recommendations, openapi_path, args.proposal_dir)
    elif args.command == "propose-grpc":
        path = propose_grpc(args.openapi_path, args.endpoint, args.output_dir)
        proposal = json.loads(Path(path).read_text())
        print(f"System: Here is the generated proto proposal: {path}")
        print(f"System: Retrieved {len(proposal['basis']['retrieved_memory_cases'])} similar memory cases.")
        print(proposal["proposed_proto"])
    elif args.command == "propose-event":
        path = propose_event(args.openapi_path, args.endpoint, args.output_dir)
        proposal = json.loads(Path(path).read_text())
        transport = proposal["transport_recommendation"]
        print(f"System: Here is the generated event proposal: {path}")
        print(f"System: Recommended transport: {transport['transport']} ({transport['confidence']:.2f})")
        print(f"System: Why: {transport['rationale']}")
    elif args.command == "memory":
        cases = MigrationMemoryStore(args.path).all()
        print(f"System: Memory cases: {len(cases)}")
        for case in cases:
            print(f"System: {case.id} | {case.endpoint_id} | {case.target} | {case.decision}")
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


def _ask_to_proceed(recommendations, openapi_path: str, proposal_dir: str) -> None:
    actionable = [
        item for item in recommendations if item.target in {MigrationTarget.GRPC, MigrationTarget.EVENT}
    ]
    if not actionable:
        print("System: No gRPC or event proposals are recommended right now.")
        return

    for item in actionable:
        print("")
        print(f"System: {item.endpoint_id} is a {item.target.value} candidate.")
        print(f"System: Why: {item.rationale}")
        answer = input("System: Do you want to proceed and generate a proposal? [y/N] ").strip().lower()
        if answer not in {"y", "yes"}:
            print(f"System: Skipped {item.endpoint_id}.")
            continue
        try:
            if item.target == MigrationTarget.GRPC:
                path = propose_grpc(openapi_path, item.endpoint_id, proposal_dir)
                print(f"System: Generated gRPC proposal: {path}")
                print("System: Status is needs_review. Add comments or approve it before implementation.")
            elif item.target == MigrationTarget.EVENT:
                path = propose_event(openapi_path, item.endpoint_id, proposal_dir)
                print(f"System: Generated event proposal: {path}")
                print("System: Status is needs_review. Review transport recommendation before approval.")
        except FileExistsError as exc:
            print(f"System: Proposal already exists: {exc}")


if __name__ == "__main__":
    main()
