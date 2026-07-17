"""validate stage: cleaning_plan + output data → diagnostics/report.

IN:  cleaning_plan.json and an existing output dataset
OUT: diagnostics/report for the existing output
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parents[1]
REPO_ROOT = SKILL_ROOT.parents[1]
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

from scripts.envs.python.diagnostics import critical_variable_diagnostics, key_diagnostics  # noqa: E402
from scripts.envs.python.io import read_data  # noqa: E402
from scripts.workflow.contracts import validate_plan  # noqa: E402
from scripts.workflow.report import render_report  # noqa: E402
from scripts.workflow.runtime import default_output_dir, ensure_dir, write_json  # noqa: E402


def validate_existing(plan_path: Path, data_path: Path) -> dict[str, Any]:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    validate_plan(plan)
    df = read_data(data_path)
    target = plan.get("target", {})
    validation = plan.get("validation", {})
    required_missing = [var for var in target.get("required_vars", []) if var not in df.columns]
    key_diag = key_diagnostics(df, target.get("key", []))
    critical_diag = critical_variable_diagnostics(df, target.get("critical_vars", []))
    failures: list[str] = []
    if required_missing:
        failures.append("required_columns_missing")
    if key_diag["missing_columns"]:
        failures.append("target_key_columns_missing")
    if key_diag["missing_rows"]:
        failures.append("target_key_missing")
    if validation.get("require_unique_target_key", True) and not key_diag["unique"]:
        failures.append("duplicate_target_key")
    max_missing = validation.get("max_critical_missing_rate")
    if max_missing is not None:
        for rate in critical_diag["missing_rates"].values():
            if rate is not None and rate > max_missing:
                failures.append("critical_missing_rate_above_threshold")
                break
    diagnostics: dict[str, Any] = {
        "status": "pass" if not failures else "fail",
        "hard_gate_failures": sorted(set(failures)),
        "output": {
            "path": str(data_path),
            "paths": [str(data_path)],
            "rows": int(len(df)),
            "columns": int(len(df.columns)),
            "required_columns_missing": required_missing,
        },
        "target_key": key_diag,
        "merges": [],
        "critical_variables": critical_diag,
        "row_flow": [],
        "reproducibility": {
            "raw_files_unchanged": None,
            "plan_path": str(plan_path),
            "output_paths": [str(data_path)],
        },
    }
    output_dir = default_output_dir(REPO_ROOT)
    ensure_dir(output_dir)
    shutil.copyfile(plan_path, output_dir / "cleaning_plan.json")
    write_json(output_dir / "cleaning_diagnostics.json", diagnostics)
    (output_dir / "cleaning_report.md").write_text(render_report(plan, diagnostics), encoding="utf-8")
    return diagnostics
