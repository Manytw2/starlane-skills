"""Run the Starlane regression quick-start demo.

This launcher is intentionally a thin shell: it only prepares demo inputs and
calls the same `run_stage.py` entry the skill workflow uses, so the demo
exercises the real summary/final pipeline instead of maintaining a duplicate.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUICK_START = Path(__file__).resolve().parent
SKILL_ROOT = ROOT / "skills" / "starlane-regression"
RUN_STAGE = SKILL_ROOT / "scripts" / "workflow" / "run_stage.py"
DEMO_DTA = QUICK_START / "demo.dta"
PUBLIC_OUTPUT = ROOT / "output" / "starlane-regression"
UV_PYTHON = ["uv", "run", "--project", str(SKILL_ROOT), "python"]

SUMMARY_ARGS = {
    "data_path": str(DEMO_DTA),
    "outcomes": ["lnApplyG", "lnGrantG"],
    "explanatory_vars": ["Attention"],
    "controls": {
        "search_pool": ["Scale", "Lev", "lnAge", "Tange", "Cash", "ROA", "SOE", "Top1", "Inst"],
        "always_include": ["Scale", "Lev", "lnAge", "ROA"],
        "min_count": 5,
    },
    "panel": {
        "entity": "id",
        "time": "year",
    },
    "robustness": {
        "alternative_outcomes": ["lnAGreenInv", "lnGGreenInv"],
        "alternative_explanatory_vars": [],
        "lag_periods": [1],
        "ln_y": False,
        "ln_x": False,
        "sample_window": None,
    },
    "mechanism": {
        "variables": ["Charge", "Subsidy", "lnCSR"],
    },
    "moderation": {
        "variables": ["OverSea", "lnMediaPos", "lnMediaNeg"],
    },
    "heterogeneity": {
        "discrete_groups": [],
        "selected_values": {},
    },
    "iv": {
        "instruments": ["Thermalinv"],
    },
    "execution": {
        "coef_direction": "positive",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Starlane quick-start demo.")
    parser.add_argument(
        "--env",
        choices=("python", "stata", "both"),
        default="python",
        help="Execution env to run. Defaults to python.",
    )
    return parser.parse_args()


def run_stage(stage_args: list[str]) -> None:
    result = subprocess.run([*UV_PYTHON, str(RUN_STAGE), *stage_args], cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def write_json(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def first_summary_row(summary_path: Path) -> dict[str, str]:
    with summary_path.open(newline="", encoding="utf-8") as f:
        rows = csv.DictReader(f)
        first = next(rows, None)
    if first is None:
        raise SystemExit(f"No rows were produced in {summary_path}")
    return first


def print_outputs(env_name: str) -> None:
    env_output_dir = PUBLIC_OUTPUT / env_name
    print(f"\n{env_name} env outputs:", flush=True)
    for path in sorted(env_output_dir.iterdir()):
        if path.is_file():
            print(f"- {path.relative_to(ROOT)}", flush=True)


def run_env(env_name: str, workdir: Path) -> None:
    args_json = write_json(workdir / f"regression_args_{env_name}.json", SUMMARY_ARGS)

    print(f"\nRunning {env_name} env summary...", flush=True)
    run_stage(["summary", "--env", env_name, "--args-json", str(args_json)])

    # Demo-only shortcut: the summary table is sorted by score descending, so
    # the first row is the top-scored candidate. Real workflows must confirm
    # the candidate with the user instead of auto-picking the highest score;
    # see SKILL.md "Model Selection, Ethics, And Boundaries".
    summary_csv = PUBLIC_OUTPUT / env_name / "combination_summary.csv"
    first = first_summary_row(summary_csv)
    selection_json = write_json(
        workdir / f"selected_candidate_{env_name}.json",
        {"cv_idx": int(first["cv_idx"]), "vce_idx": int(first["vce_idx"])},
    )

    print(f"\nRunning {env_name} env final stage...", flush=True)
    run_stage(["final", "--env", env_name, "--args-json", str(args_json), "--selection-json", str(selection_json)])

    print_outputs(env_name)


def main() -> int:
    args = parse_args()
    if not DEMO_DTA.exists():
        raise SystemExit(f"Demo dataset not found: {DEMO_DTA}")

    envs = ("python", "stata") if args.env == "both" else (args.env,)
    with tempfile.TemporaryDirectory(prefix="starlane-demo-") as tmp:
        for env_name in envs:
            run_env(env_name, Path(tmp))

    print(f"\nQuick start complete. Output root: {PUBLIC_OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
