"""Unified stage runner for the starlane-data-cleaner skill."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parents[1]
REPO_ROOT = SKILL_ROOT.parents[1]
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

from scripts.workflow.execute_plan import run_plan  # noqa: E402
from scripts.workflow.profile_data import profile_inputs  # noqa: E402
from scripts.workflow.validate_output import validate_existing  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run starlane-data-cleaner workflow stages.")
    subparsers = parser.add_subparsers(dest="stage", required=True)

    profile = subparsers.add_parser("profile", help="Profile declared input datasets.")
    profile.add_argument("--inputs-json", required=True, type=Path)

    run = subparsers.add_parser("run", help="Execute a cleaning plan and validate output.")
    run.add_argument("--plan", required=True, type=Path)

    validate = subparsers.add_parser("validate", help="Validate an existing output dataset.")
    validate.add_argument("--plan", required=True, type=Path)
    validate.add_argument("--data", required=True, type=Path)

    return parser


def print_result(result: dict) -> None:
    print(json.dumps({"status": result.get("status", "ok"), "hard_gate_failures": result.get("hard_gate_failures", [])}, ensure_ascii=False))


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.stage == "profile":
        result = profile_inputs(args.inputs_json, REPO_ROOT)
        print(json.dumps({"status": "ok", "input_count": len(result["inputs"])}, ensure_ascii=False))
        return 0
    if args.stage == "run":
        result = run_plan(args.plan, REPO_ROOT)
        print_result(result)
        return 0 if result.get("status") == "pass" else 2
    if args.stage == "validate":
        result = validate_existing(args.plan, args.data)
        print_result(result)
        return 0 if result.get("status") == "pass" else 2
    parser.error(f"Unknown stage: {args.stage}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
