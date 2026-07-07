"""Python summary backend for Starlane regression.

The output contract matches combination_summary.csv.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from regression_backend_common import (
    RegressionArgs,
    apply_spec_condition,
    build_specs,
    compute_cv_subsets,
    encode_panel_if_needed,
    ensure_columns,
    fail,
    format_coef,
    make_base_sample,
    prepare_backend_data,
    parse_cli_values,
    read_data,
    run_spec,
    spec_required_columns,
    split_words,
    stars_for_result,
    vce_suffix,
    write_csv,
)


def main() -> int:
    try:
        values, _ = parse_cli_values(sys.argv)
        args = RegressionArgs.from_list(values)
        cv_idx_start = int(values[18]) if len(values) > 18 and values[18].strip() else None
        cv_idx_end = int(values[19]) if len(values) > 19 and values[19].strip() else None

        y_vars = split_words(args.y)
        x_vars = split_words(args.x)
        cv_all = split_words(args.cv)
        cv_fixed = split_words(args.cv_fixed)
        cv_min_count = int(args.cv_min_count.strip() or "0")
        coef_direction = (args.coef_direction.strip().lower() or "positive")
        if coef_direction not in ("positive", "negative"):
            raise ValueError("coef_direction must be positive or negative")

        optional_originals = split_words(args.meds) + split_words(args.mods) + split_words(args.iv)
        required = [*y_vars, *x_vars, *cv_all, args.panelvar, args.timevar, *optional_originals]
        df = read_data(args.input_dta)
        ensure_columns(df, required)
        df = prepare_backend_data(df, args)
        df, panelvar = encode_panel_if_needed(df, args.panelvar)
        timevar = args.timevar

        export_dir = Path(os.environ.get("STARLANE_EXPORT", ".starlane"))
        temp_dir = Path(os.environ.get("STARLANE_TMP", ".starlane/tmp"))
        export_dir.mkdir(parents=True, exist_ok=True)
        temp_dir.mkdir(parents=True, exist_ok=True)

        cv_subsets = compute_cv_subsets(cv_all, cv_fixed, cv_min_count)
        all_specs = build_specs(args, cv_all)
        columns = ["selection_id", "cv_idx", "vce_idx", "vce_suffix", "cv_selected", "score"]
        columns.extend(spec.column for spec in all_specs)
        rows: list[dict[str, str]] = []

        loop_items = list(enumerate(cv_subsets))
        if cv_idx_start is not None and cv_idx_end is not None:
            loop_items = [(i, subset) for i, subset in loop_items if cv_idx_start <= i <= cv_idx_end]

        for cv_idx, cv_subset in loop_items:
            specs = build_specs(args, cv_subset)
            sample_vars = [panelvar, timevar, *spec_required_columns(specs)]
            ensure_columns(df, sample_vars)
            base_sample = make_base_sample(df, sample_vars)
            if int(base_sample.sum()) < 30:
                continue
            for vce_idx in range(4):
                row: dict[str, str] = {
                    "selection_id": f"{cv_idx}_{vce_idx}",
                    "cv_idx": str(cv_idx),
                    "vce_idx": str(vce_idx),
                    "vce_suffix": vce_suffix(vce_idx, panelvar, timevar),
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
                    result = run_spec(df, spec, panelvar, timevar, vce_idx, spec_sample)
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
                        result = run_spec(df, spec, panelvar, timevar, vce_idx, spec_sample)
                        stars = stars_for_result(result, coef_direction)
                        score += stars
                        row[spec.column] = format_coef(result, stars)
                row["score"] = str(score)
                rows.append(row)

        rows.sort(key=lambda r: (-float(r["score"]), int(r["cv_idx"]), int(r["vce_idx"])))
        out = export_dir / "combination_summary.csv"
        write_csv(out, rows, columns)
        print(f"STARLANE_OUTPUT: {out}")
        return 0
    except Exception as e:
        return fail(str(e))


if __name__ == "__main__":
    sys.exit(main())
