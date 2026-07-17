"""run stage: cleaning_plan → analysis data, diagnostics, report.

IN:  cleaning_plan.json   structured data-cleaning and merge plan
OUT: analysis dataset     user-facing cleaned data
OUT: diagnostics/report   JSON diagnostics and Markdown report
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parents[1]
REPO_ROOT = SKILL_ROOT.parents[1]
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

from scripts.envs.python.diagnostics import (  # noqa: E402
    critical_variable_diagnostics,
    dataframe_profile,
    key_diagnostics,
)
from scripts.envs.python.io import read_data, write_data  # noqa: E402
from scripts.workflow.contracts import resolve_path, validate_plan  # noqa: E402
from scripts.workflow.report import render_report  # noqa: E402
from scripts.workflow.runtime import default_output_dir, ensure_dir, file_sha256, write_json  # noqa: E402


class PlanExecutor:
    def __init__(self, plan: dict[str, Any], plan_path: Path, cwd: Path) -> None:
        validate_plan(plan)
        self.plan = plan
        self.plan_path = plan_path
        self.cwd = cwd
        self.output_dir = self._output_dir()
        self.datasets: dict[str, pd.DataFrame] = {}
        self.input_hashes: dict[str, str] = {}
        self.row_flow: list[dict[str, Any]] = []
        self.merges: list[dict[str, Any]] = []
        self.current_dataset: str | None = None

    def _output_dir(self) -> Path:
        output = self.plan.get("output", {})
        directory = output.get("directory")
        if directory:
            return resolve_path(directory, self.cwd)
        return default_output_dir(REPO_ROOT)

    def execute(self) -> dict[str, Any]:
        self._load_inputs()
        for operation in self.plan.get("operations", []):
            self._apply_operation(operation)
        output_name = self._final_dataset_name()
        final_df = self.datasets[output_name].copy()
        output_paths = self._write_outputs(final_df)
        diagnostics = self._build_diagnostics(final_df, output_paths)
        ensure_dir(self.output_dir)
        plan_public_path = self.output_dir / "cleaning_plan.json"
        shutil.copyfile(self.plan_path, plan_public_path)
        diagnostics["reproducibility"]["plan_path"] = str(plan_public_path)
        diagnostics_path = write_json(self.output_dir / "cleaning_diagnostics.json", diagnostics)
        report_path = self.output_dir / "cleaning_report.md"
        report_path.write_text(render_report(self.plan, diagnostics), encoding="utf-8")
        diagnostics["reproducibility"]["diagnostics_path"] = str(diagnostics_path)
        diagnostics["reproducibility"]["report_path"] = str(report_path)
        write_json(diagnostics_path, diagnostics)
        return diagnostics

    def _load_inputs(self) -> None:
        for item in self.plan["inputs"]:
            path = resolve_path(item["path"], self.cwd)
            if not path.exists():
                raise FileNotFoundError(path)
            self.input_hashes[item["name"]] = file_sha256(path)
            self.datasets[item["name"]] = read_data(path)
            self.current_dataset = item["name"]

    def _apply_operation(self, operation: dict[str, Any]) -> None:
        op = operation["op"]
        if op == "rename":
            df = self._dataset(operation["dataset"])
            df.rename(columns=operation["columns"], inplace=True)
        elif op == "select":
            dataset = operation["dataset"]
            self.datasets[dataset] = self._dataset(dataset)[operation["columns"]].copy()
        elif op == "drop_columns":
            df = self._dataset(operation["dataset"])
            df.drop(columns=operation["columns"], inplace=True, errors="ignore")
        elif op in {"trim", "lower", "upper"}:
            self._string_clean(operation, op)
        elif op == "cast":
            self._cast(operation)
        elif op == "pad":
            self._pad(operation)
        elif op == "replace_missing":
            self._replace_missing(operation)
        elif op == "drop_duplicates":
            self._drop_duplicates(operation)
        elif op == "filter":
            self._filter(operation)
        elif op == "append":
            self._append(operation)
        elif op == "merge":
            self._merge(operation)
        elif op == "set_output":
            self.current_dataset = operation["dataset"]
        else:
            raise ValueError(f"Unsupported operation: {op}")

    def _dataset(self, name: str) -> pd.DataFrame:
        if name not in self.datasets:
            raise ValueError(f"Unknown dataset: {name}")
        return self.datasets[name]

    def _string_clean(self, operation: dict[str, Any], op: str) -> None:
        df = self._dataset(operation["dataset"])
        for column in operation["columns"]:
            values = df[column].astype("string")
            if op == "trim":
                df[column] = values.str.strip()
            elif op == "lower":
                df[column] = values.str.lower()
            else:
                df[column] = values.str.upper()

    def _cast(self, operation: dict[str, Any]) -> None:
        df = self._dataset(operation["dataset"])
        for column, cast_type in operation["columns"].items():
            if cast_type == "string":
                df[column] = df[column].astype("string")
            elif cast_type == "int":
                df[column] = pd.to_numeric(df[column], errors="coerce").astype("Int64")
            elif cast_type == "float":
                df[column] = pd.to_numeric(df[column], errors="coerce")
            elif cast_type == "date":
                df[column] = pd.to_datetime(df[column], errors="coerce")

    def _pad(self, operation: dict[str, Any]) -> None:
        df = self._dataset(operation["dataset"])
        for column, width in operation["columns"].items():
            df[column] = df[column].astype("string").str.strip().str.zfill(int(width))

    def _replace_missing(self, operation: dict[str, Any]) -> None:
        df = self._dataset(operation["dataset"])
        values = operation["values"]
        for column in operation["columns"]:
            df[column] = df[column].replace(values, pd.NA)

    def _drop_duplicates(self, operation: dict[str, Any]) -> None:
        dataset = operation["dataset"]
        df = self._dataset(dataset)
        key = operation["key"]
        before = len(df)
        duplicate_count = int(df.duplicated(key, keep=False).sum())
        method = operation.get("method", "error")
        if duplicate_count and method == "error":
            raise ValueError(f"{dataset} has {duplicate_count} duplicate rows by {key}")
        if method == "keep_first":
            self.datasets[dataset] = df.drop_duplicates(key, keep="first").copy()
        elif method == "keep_last":
            self.datasets[dataset] = df.drop_duplicates(key, keep="last").copy()
        after = len(self.datasets[dataset])
        self._record_flow(
            step=f"drop_duplicates:{dataset}",
            before=before,
            after=after,
            reason=operation.get("reason"),
        )

    def _filter(self, operation: dict[str, Any]) -> None:
        reason = operation.get("reason")
        if not reason:
            raise ValueError("filter operations must include reason")
        dataset = operation["dataset"]
        df = self._dataset(dataset)
        before = len(df)
        filtered = df.query(operation["expr"]).copy()
        self.datasets[dataset] = filtered
        self._record_flow(step=f"filter:{dataset}", before=before, after=len(filtered), reason=reason)

    def _append(self, operation: dict[str, Any]) -> None:
        frames = [self._dataset(name) for name in operation["datasets"]]
        before = sum(len(frame) for frame in frames)
        result = pd.concat(frames, ignore_index=True, sort=False)
        name = operation["name"]
        self.datasets[name] = result
        self.current_dataset = name
        self._record_flow(step=f"append:{name}", before=before, after=len(result), reason="append datasets")

    def _merge(self, operation: dict[str, Any]) -> None:
        left_name = operation["left"]
        right_name = operation["right"]
        left = self._dataset(left_name)
        right = self._dataset(right_name)
        keys = operation["keys"]
        merge_type = operation["type"]
        self._validate_merge_keys(left, right, keys, merge_type, operation.get("name", "merge"))
        left_rows = len(left)
        right_rows = len(right)
        all_matches = left.merge(right, on=keys, how="outer", indicator=True, suffixes=("", f"_{right_name}"))
        all_counts = all_matches["_merge"].value_counts()
        matched = int(all_counts.get("both", 0))
        left_only = int(all_counts.get("left_only", 0))
        right_only = int(all_counts.get("right_only", 0))
        merged = left.merge(right, on=keys, how="left", indicator=True, suffixes=("", f"_{right_name}"))
        unmatched = operation.get("unmatched", "keep_left_with_flag")
        if unmatched == "keep_matched":
            result = merged[merged["_merge"] == "both"].copy()
        elif unmatched == "keep_all_with_flag":
            result = all_matches.copy()
        else:
            result = merged.copy()
        result.rename(columns={"_merge": f"{operation.get('name', 'merge')}_flag"}, inplace=True)
        name = operation.get("name", f"{left_name}_{right_name}")
        self.datasets[name] = result
        self.current_dataset = name
        rows_after = len(result)
        merge_diag = {
            "name": name,
            "type": merge_type,
            "keys": keys,
            "left_rows_before": int(left_rows),
            "right_rows_before": int(right_rows),
            "rows_after": int(rows_after),
            "matched": matched,
            "left_only": left_only,
            "right_only": right_only,
            "match_rate_left": float(matched / left_rows) if left_rows else 0.0,
            "row_expansion_ratio": float(rows_after / left_rows) if left_rows else 0.0,
        }
        self.merges.append(merge_diag)
        self._record_flow(step=f"merge:{name}", before=left_rows, after=rows_after, reason="merge datasets")

    def _validate_merge_keys(
        self,
        left: pd.DataFrame,
        right: pd.DataFrame,
        keys: list[str],
        merge_type: str,
        name: str,
    ) -> None:
        missing_left = [key for key in keys if key not in left.columns]
        missing_right = [key for key in keys if key not in right.columns]
        if missing_left or missing_right:
            raise ValueError(f"{name} merge key missing; left={missing_left}, right={missing_right}")
        if merge_type in {"1:1", "1:m"} and left.duplicated(keys).any():
            raise ValueError(f"{name} left side is not unique by {keys}")
        if merge_type in {"1:1", "m:1"} and right.duplicated(keys).any():
            raise ValueError(f"{name} right side is not unique by {keys}")

    def _record_flow(self, step: str, before: int, after: int, reason: str | None) -> None:
        dropped = max(before - after, 0)
        self.row_flow.append(
            {
                "step": step,
                "rows_before": int(before),
                "rows_after": int(after),
                "dropped": int(dropped),
                "drop_rate": float(dropped / before) if before else 0.0,
                "reason": reason,
            }
        )

    def _final_dataset_name(self) -> str:
        if self.current_dataset is None:
            raise ValueError("No dataset was produced")
        return self.current_dataset

    def _write_outputs(self, df: pd.DataFrame) -> list[str]:
        output = self.plan.get("output", {})
        dataset_name = output.get("dataset_name", "analysis_data")
        formats = output.get("formats", ["csv"])
        output_paths: list[str] = []
        for fmt in formats:
            path = self.output_dir / f"{dataset_name}.{fmt}"
            write_data(df, path, fmt)
            output_paths.append(str(path))
        return output_paths

    def _build_diagnostics(self, df: pd.DataFrame, output_paths: list[str]) -> dict[str, Any]:
        target = self.plan.get("target", {})
        validation = self.plan.get("validation", {})
        required_vars = target.get("required_vars", [])
        critical_vars = target.get("critical_vars", [])
        key = target.get("key", [])
        required_missing = [var for var in required_vars if var not in df.columns]
        key_diag = key_diagnostics(df, key)
        critical_diag = critical_variable_diagnostics(df, critical_vars)
        hard_failures = self._hard_gate_failures(df, required_missing, key_diag, critical_diag)
        first_output = output_paths[0] if output_paths else None
        diagnostics = {
            "status": "pass" if not hard_failures else "fail",
            "hard_gate_failures": hard_failures,
            "output": {
                "path": first_output,
                "paths": output_paths,
                "rows": int(len(df)),
                "columns": int(len(df.columns)),
                "required_columns_missing": required_missing,
            },
            "target_key": key_diag,
            "merges": self.merges,
            "critical_variables": critical_diag,
            "row_flow": self.row_flow,
            "profiles": {
                name: dataframe_profile(name, frame, None) for name, frame in self.datasets.items()
            },
            "reproducibility": {
                "raw_files_unchanged": self._raw_files_unchanged(),
                "input_hashes": self.input_hashes,
                "plan_path": str(self.plan_path),
                "output_paths": output_paths,
            },
        }
        if validation.get("expected_row_min") is not None:
            diagnostics["output"]["expected_row_min"] = validation["expected_row_min"]
        if validation.get("expected_row_max") is not None:
            diagnostics["output"]["expected_row_max"] = validation["expected_row_max"]
        return diagnostics

    def _hard_gate_failures(
        self,
        df: pd.DataFrame,
        required_missing: list[str],
        key_diag: dict[str, Any],
        critical_diag: dict[str, Any],
    ) -> list[str]:
        validation = self.plan.get("validation", {})
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
        max_unmatched = validation.get("max_unmatched_rate")
        if max_unmatched is not None:
            for merge in self.merges:
                unmatched_rate = 1.0 - merge["match_rate_left"]
                if unmatched_rate > max_unmatched:
                    failures.append("merge_unmatched_rate_above_threshold")
                    break
        if not validation.get("allow_row_expansion", False):
            for merge in self.merges:
                if merge["row_expansion_ratio"] > 1.000001:
                    failures.append("unexpected_row_expansion")
                    break
        if validation.get("expected_row_min") is not None and len(df) < validation["expected_row_min"]:
            failures.append("row_count_below_expectation")
        if validation.get("expected_row_max") is not None and len(df) > validation["expected_row_max"]:
            failures.append("row_count_above_expectation")
        for item in self.row_flow:
            if item["dropped"] and not item.get("reason"):
                failures.append("drop_without_reason")
                break
        if not self._raw_files_unchanged():
            failures.append("raw_files_modified")
        return sorted(set(failures))

    def _raw_files_unchanged(self) -> bool:
        for item in self.plan["inputs"]:
            path = resolve_path(item["path"], self.cwd)
            if not path.exists() or file_sha256(path) != self.input_hashes[item["name"]]:
                return False
        return True


def run_plan(plan_path: Path, cwd: Path) -> dict[str, Any]:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    return PlanExecutor(plan, plan_path, cwd).execute()
