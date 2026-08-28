"""ChangeProof unified command line interface."""
import os
import sys
import json
import argparse
from typing import Dict, Any
from changeproof.agent import ChangeProofAgent
from changeproof.verifier import verify

def prompt_human_decision(experiment_id: str) -> Dict[str, Any]:
    """Interactive human approval gate for deployment decisions."""
    print(f"\n--- ChangeProof Human Engineering Approval Gate [{experiment_id}] ---")
    print("1) Approve & Deploy Remediation")
    print("2) Reject Remediation")
    print("3) Escalate for Further Review")
    choice = input("Enter decision [1-3] (default 3): ").strip()
    
    if choice == "1":
        return {"status": "APPROVED", "action": "deploy", "experiment_id": experiment_id}
    elif choice == "2":
        return {"status": "REJECTED", "action": "block", "experiment_id": experiment_id}
    else:
        return {"status": "HOLD", "action": "escalate_for_review", "experiment_id": experiment_id}

def main():
    parser = argparse.ArgumentParser(description="ChangeProof Agentic Reliability System")
    subparsers = parser.add_subparsers(dest="command")

    # Command: run
    run_parser = subparsers.add_parser("run", help="Run ChangeProof evaluation on a PR diff")
    run_parser.add_argument("--pr", required=True, help="Path to unified diff patch file")

    # Command: verify
    verify_parser = subparsers.add_parser("verify", help="Run deterministic verifier")
    verify_parser.add_argument("--pre", required=True, help="Pre-patch metrics CSV")
    verify_parser.add_argument("--post", required=True, help="Post-patch metrics CSV")
    verify_parser.add_argument("--spec", required=True, help="Experiment YAML spec")

    args = parser.parse_args()

    if args.command == "run":
        if not os.path.exists(args.pr):
            print(f"Error: PR diff file not found: {args.pr}")
            sys.exit(1)
        with open(args.pr, "r", encoding="utf-8") as f:
            diff_text = f.read()

        agent = ChangeProofAgent()
        result = agent.run_investigation(diff_text)
        print(json.dumps(result, indent=2))

    elif args.command == "verify":
        import yaml
        with open(args.spec, "r", encoding="utf-8") as f:
            spec = yaml.safe_load(f)
        ver_res = verify(args.pre, args.post, spec.get("assertions", {}))
        print(json.dumps(ver_res.to_dict(), indent=2))

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
