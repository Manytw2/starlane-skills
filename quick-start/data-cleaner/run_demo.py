"""Run the Starlane data-cleaner quick-start demo.

The demo creates two small raw files, writes a cleaning plan, and calls the
same `run_stage.py` entry the skill workflow uses.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DEMO_ROOT = Path(__file__).resolve().parent
RAW_DIR = DEMO_ROOT / "raw"
SKILL_ROOT = ROOT / "skills" / "starlane-data-cleaner"
RUN_STAGE = SKILL_ROOT / "scripts" / "workflow" / "run_stage.py"
PUBLIC_OUTPUT = ROOT / "output" / "starlane-data-cleaner" / "python"
UV_PYTHON = ["uv", "run", "--project", str(SKILL_ROOT), "python"]


def write_demo_data() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    firm_basic = pd.DataFrame(
        {
            "FirmID": ["001", "002", "003", "004", "005"],
            "年份": [2020, 2020, 2020, 2020, 2020],
            "Y": [1.2, 2.4, 3.1, 4.0, 5.5],
            "X": [10, 12, 11, 15, 18],
        }
    )
    finance = pd.DataFrame(
        {
            "firm_id": ["1 ", "2 ", "3 ", "4 ", "6 "],
            "year": ["2020", "2020", "2020", "2020", "2020"],
            "asset": [100, 130, 90, 160, 200],
        }
    )
    firm_basic.to_csv(RAW_DIR / "firm_basic.csv", index=False)
    finance.to_csv(RAW_DIR / "finance.csv", index=False)


def cleaning_plan() -> dict:
    return {
        "target": {
            "unit": "firm-year",
            "key": ["firm_id", "year"],
            "required_vars": ["firm_id", "year", "y", "x", "asset"],
            "critical_vars": ["y", "x", "asset"],
        },
        "inputs": [
            {"name": "firm_basic", "path": str(RAW_DIR / "firm_basic.csv"), "role": "master"},
            {"name": "finance", "path": str(RAW_DIR / "finance.csv"), "role": "using"},
        ],
        "operations": [
            {
                "op": "rename",
                "dataset": "firm_basic",
                "columns": {"FirmID": "firm_id", "年份": "year", "Y": "y", "X": "x"},
            },
            {"op": "cast", "dataset": "firm_basic", "columns": {"firm_id": "string", "year": "int"}},
            {"op": "pad", "dataset": "firm_basic", "columns": {"firm_id": 3}},
            {"op": "cast", "dataset": "finance", "columns": {"firm_id": "string", "year": "int"}},
            {"op": "trim", "dataset": "finance", "columns": ["firm_id"]},
            {"op": "pad", "dataset": "finance", "columns": {"firm_id": 3}},
            {
                "op": "merge",
                "name": "merge_finance",
                "left": "firm_basic",
                "right": "finance",
                "type": "m:1",
                "keys": ["firm_id", "year"],
                "unmatched": "keep_left_with_flag",
            },
            {"op": "set_output", "dataset": "merge_finance"},
        ],
        "validation": {
            "require_unique_target_key": True,
            "max_critical_missing_rate": 0.25,
            "max_unmatched_rate": 0.25,
            "allow_row_expansion": False,
        },
        "output": {
            "dataset_name": "analysis_data",
            "formats": ["csv"],
            "directory": str(PUBLIC_OUTPUT),
        },
    }


def run_stage(stage_args: list[str]) -> None:
    result = subprocess.run([*UV_PYTHON, str(RUN_STAGE), *stage_args], cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> int:
    write_demo_data()
    plan_path = DEMO_ROOT / "cleaning_plan.json"
    plan_path.write_text(json.dumps(cleaning_plan(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("Running data-cleaner demo...", flush=True)
    run_stage(["run", "--plan", str(plan_path)])

    print("\nData-cleaner outputs:", flush=True)
    for path in sorted(PUBLIC_OUTPUT.iterdir()):
        if path.is_file():
            print(f"- {path.relative_to(ROOT)}", flush=True)
    print(f"\nQuick start complete. Output root: {PUBLIC_OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
