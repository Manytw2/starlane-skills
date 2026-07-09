"""Python summary env for Starlane regression.

The output contract matches combination_summary.csv.
"""

from __future__ import annotations

import os
import sys
import json
from pathlib import Path
from typing import Any

from common import (
    RegressionArgs,
    apply_spec_condition,
    build_model_plan,
    encode_panel_if_needed,
    ensure_columns,
    fail,
    format_coef,
    load_regression_args_json,
    make_base_sample,
    prepare_regression_data,
    reject_positional_args,
    read_data,
    run_spec_attempt,
    spec_required_columns,
    split_words,
    stars_for_result,
    write_csv,
)


class ProgressLogger:
    def __init__(self, path: str | None) -> None:
        self.path = Path(path) if path else None
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def event(self, event: str, **fields: Any) -> None:
        if not self.path:
            return
        payload = {"event": event, **fields}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> int:
    progress = ProgressLogger(os.environ.get("STARLANE_PROGRESS_LOG"))
    try:
        reject_positional_args(sys.argv)
        import argparse

        parser = argparse.ArgumentParser(description="Run Starlane Python summary from regression_args.json.")
        parser.add_argument("--args-json", required=True, help="Path to regression_args.json")
        parser.add_argument("--cv-idx-start", type=int, help="Optional first control-combination index")
        parser.add_argument("--cv-idx-end", type=int, help="Optional final control-combination index, inclusive")
        ns = parser.parse_args(sys.argv[1:])

        values = load_regression_args_json(ns.args_json)
        args = RegressionArgs.from_mapping(values)
        cv_idx_start = ns.cv_idx_start
        cv_idx_end = ns.cv_idx_end

        y_vars = split_words(args.y)
        x_vars = split_words(args.x)
        cv_all = split_words(args.cv)
        coef_direction = (args.coef_direction.strip().lower() or "positive")
        if coef_direction not in ("positive", "negative"):
            raise ValueError("coef_direction must be positive or negative")

        optional_originals = split_words(args.meds) + split_words(args.mods) + split_words(args.iv)
        required = [*y_vars, *x_vars, *cv_all, args.panelvar, args.timevar, *optional_originals]
        df = read_data(args.input_dta)
        ensure_columns(df, required)
        df = prepare_regression_data(df, args)
        df, panelvar = encode_panel_if_needed(df, args.panelvar)
        timevar = args.timevar

        export_dir = Path(os.environ.get("STARLANE_EXPORT", ".starlane"))
        temp_dir = Path(os.environ.get("STARLANE_TMP", ".starlane/tmp"))
        export_dir.mkdir(parents=True, exist_ok=True)
        temp_dir.mkdir(parents=True, exist_ok=True)

        plan = build_model_plan(args)
        columns = list(plan.summary_columns)
        rows: list[dict[str, str]] = []

        loop_items = [(subset.cv_idx, list(subset.controls)) for subset in plan.cv_subsets]
        if cv_idx_start is not None and cv_idx_end is not None:
            loop_items = [(i, subset) for i, subset in loop_items if cv_idx_start <= i <= cv_idx_end]
        vce_choices = list(plan.vce_choices)
        total_candidates = len(loop_items) * len(vce_choices)
        completed_candidates = 0
        progress.event(
            "summary_progress_initialized",
            total_candidates=total_candidates,
            effective_cv_subset_count=len(loop_items),
            vce_count=len(vce_choices),
        )

        for cv_idx, cv_subset in loop_items:
            specs = list(plan.specs_for_cv_idx(args, cv_idx))
            sample_vars = [panelvar, timevar, *spec_required_columns(specs)]
            ensure_columns(df, sample_vars)
            base_sample = make_base_sample(df, sample_vars)
            if int(base_sample.sum()) < 30:
                for choice in vce_choices:
                    completed_candidates += 1
                    progress.event(
                        "summary_progress",
                        current_candidate=completed_candidates,
                        total_candidates=total_candidates,
                        percent_complete=round((completed_candidates / total_candidates) * 100, 2) if total_candidates else 100.0,
                        cv_idx=cv_idx,
                        vce_idx=choice.vce_idx,
                    )
                    progress.event(
                        "cv_subset_skipped",
                        cv_idx=cv_idx,
                        vce_idx=choice.vce_idx,
                        reason="sample_below_min_n",
                        nobs=int(base_sample.sum()),
                    )
                continue
            for choice in vce_choices:
                completed_candidates += 1
                progress.event(
                    "summary_progress",
                    current_candidate=completed_candidates,
                    total_candidates=total_candidates,
                    percent_complete=round((completed_candidates / total_candidates) * 100, 2) if total_candidates else 100.0,
                    cv_idx=cv_idx,
                    vce_idx=choice.vce_idx,
                )
                row: dict[str, str] = {
                    "selection_id": f"{cv_idx}_{choice.vce_idx}",
                    "cv_idx": str(cv_idx),
                    "vce_idx": str(choice.vce_idx),
                    "vce_suffix": choice.suffix,
                    "cv_selected": "|".join(cv_subset),
                    "score": "0",
                }
                for spec in specs:
                    row[spec.column] = ""
                score = 0
                any_sig_cv = False
                any_dir_ok = False
                for spec in specs:
                    if not spec.section.startswith("baseline"):
                        continue
                    spec_sample = apply_spec_condition(df, base_sample, spec)
                    attempt = run_spec_attempt(df, spec, panelvar, timevar, choice.vce_idx, spec_sample)
                    result = attempt.result
                    if result is None:
                        progress.event(
                            "spec_result_missing",
                            cv_idx=cv_idx,
                            vce_idx=choice.vce_idx,
                            vce_suffix=row["vce_suffix"],
                            section=spec.section,
                            column=spec.column,
                            reason=attempt.reason,
                            detail=attempt.detail or {},
                        )
                    stars = stars_for_result(result, coef_direction)
                    score += stars
                    row[spec.column] = format_coef(result, stars)
                    if spec.section == "baseline_cv" and result is not None:
                        if stars > 0:
                            any_sig_cv = True
                        if (coef_direction == "positive" and result.coef > 0) or (coef_direction == "negative" and result.coef < 0):
                            any_dir_ok = True
                if any_sig_cv and any_dir_ok:
                    for spec in specs:
                        if spec.section.startswith("baseline"):
                            continue
                        spec_sample = apply_spec_condition(df, base_sample, spec)
                        attempt = run_spec_attempt(df, spec, panelvar, timevar, choice.vce_idx, spec_sample)
                        result = attempt.result
                        if result is None:
                            progress.event(
                                "spec_result_missing",
                                cv_idx=cv_idx,
                                vce_idx=choice.vce_idx,
                                vce_suffix=row["vce_suffix"],
                                section=spec.section,
                                column=spec.column,
                                reason=attempt.reason,
                                detail=attempt.detail or {},
                            )
                        stars = stars_for_result(result, coef_direction)
                        score += stars
                        row[spec.column] = format_coef(result, stars)
                else:
                    for spec in specs:
                        if spec.section.startswith("baseline"):
                            continue
                        progress.event(
                            "section_skipped",
                            cv_idx=cv_idx,
                            vce_idx=choice.vce_idx,
                            vce_suffix=row["vce_suffix"],
                            section=spec.section,
                            column=spec.column,
                            reason="baseline_gate_not_met",
                        )
                row["score"] = str(score)
                rows.append(row)

        rows.sort(key=lambda r: (-float(r["score"]), int(r["cv_idx"]), int(r["vce_idx"])))
        out = export_dir / "combination_summary.csv"
        write_csv(out, rows, columns)
        progress.event("summary_csv_written", path=str(out), rows=len(rows))
        print(f"STARLANE_OUTPUT: {out}")
        return 0
    except Exception as e:
        progress.event("stage_failed", error=str(e))
        return fail(str(e))


if __name__ == "__main__":
    sys.exit(main())
