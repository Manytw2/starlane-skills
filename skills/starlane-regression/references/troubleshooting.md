# Troubleshooting

Use this file for workflow-level and env failures.

Starlane has one workflow and multiple envs. First decide whether the failure is workflow-level, env-specific, or a summary/final selection mismatch.

## Workflow-Level Issues

- data path does not exist
- unsupported input format
- `analysis_plan` is missing required sections
- `analysis_plan` references variables not present in the data profile
- `cv_fixed` is not a subset of the control-variable pool
- `coef_direction` is not `positive` or `negative`
- selected `cv_idx` or `vce_idx` does not come from the current summary table
- user asks for an unsupported method such as DID, RDD, PSM, SCM, DML, or event study

## Python Target Issues

- `uv` is unavailable: install or activate `uv`, or run from an environment where skill scripts can be invoked through `uv run --project <skill-root> python`.
- Data import fails: confirm the file extension is `.dta`, `.csv`, `.xlsx`, or `.xls`; for `.dta`, confirm `pyreadstat`/pandas support the file.
- Missing dependency: confirm `numpy`, `pandas`, `pyfixest`, `pyreadstat`, and `python-docx` are declared in the skill-local `pyproject.toml` and run through `uv run --project <skill-root> python`.
- Summary progress: inspect `.starlane/runtime/starlane-regression/runs/<run-id>/logs/progress.jsonl` for `current_candidate`, `total_candidates`, and `percent_complete`.
- Empty summary cells: inspect `spec_result_missing`, `section_skipped`, and `cv_subset_skipped` events in `progress.jsonl`.
- Word export fails: confirm `python-docx` is installed and the output path is writable.
- Generated source runs in the wrong directory: run it from the skill directory or use absolute paths in the generated source.
- Summary succeeds but final fails: confirm final uses the same `regression_args.json` object and a `selected_candidate.json` whose `cv_idx`/`vce_idx` came from the same `combination_summary.csv`.

## Stata Target Issues

Common Stata errors:

- `r(601)`: input file path is wrong or Stata cannot access the file.
- `r(111)`: a mapped variable does not exist.
- `r(109)`: a numeric operation was applied to a string variable.
- `r(198)`: a generated Stata command has invalid syntax or an invalid option value.

Missing packages:

- `reghdfe` missing: run `ssc install reghdfe`.
- `ivreghdfe` missing: run `ssc install ivreghdfe`.
- `reg2docx` or `sum2docx` missing: install the required Stata export package before running the generated final `.do`.

Stata runtime files:

- Stata batch logs should be under `.starlane/runtime/starlane-regression/runs/<run-id>/logs/`, not the repository root.
- The generated wrapper `.do` should be under the run's `generated/` directory.
- `STARLANE_EXPORT` should point to the run's `outputs/` directory.
- `STARLANE_TMP` should point to the run's `tmp/` directory.
- Successful runs should clean low-value tmp files such as `.score_*.dta`.
- Failed runs may keep tmp files and logs for diagnosis.

Runtime maintenance:

- Inspect `.starlane/runtime/starlane-regression/runs/<run-id>/run.json` for run status, paths, and errors.
- Delete old run directories only after checking their `run.json` manifests.
- Runtime cleanup must not delete `output/starlane-regression/`.

## Summary-Final Selection Issues

If summary generation succeeds but final generation fails, check that:

- the same confirmed analysis plan or same compiled `regression_args.json` object was reused
- `cv_idx` and `vce_idx` came from the same `combination_summary.csv`
- the selected env is the same env intended for final source generation
- the generated source file points to a writable output path

## Heterogeneity Group Ns Do Not Sum To Full-Sample N

Expected when the group variable is time-varying: subsample splits create new
singleton fixed effects, which `reghdfe`/`pyfixest` drop. See "Group N vs
Full-Sample N" in `references/models/heterogeneity.md`.

## Result Difference Diagnosis

Do not debug Python and Stata results by forcing coefficient-by-coefficient equality.

Investigate:

- estimator package and version
- fixed-effect implementation
- VCE implementation
- degrees-of-freedom correction
- missing-data sample
- sorting or lag construction
- Stata command choices and user-written package versions

## Python Summary Reason Codes

| Reason | Meaning | Suggested check |
| --- | --- | --- |
| `sample_below_min_n` | The candidate model has fewer than 30 complete observations. | Check missingness and whether too many controls or subgroup filters are active. |
| `zero_variance_regressor` | A regressor has no usable variation in the candidate sample. | Check transformed variables, subgroup filters, and lag/log construction. |
| `linear_algebra_failed` | The estimator hit a matrix-rank or numerical solve failure. | Check collinearity among controls, fixed effects, and the target variable. |
| `non_finite_values` | The fitted result did not produce a finite target coefficient. | Check infinite values, log transforms, and extreme missingness. |
| `pyfixest_failed` | `pyfixest` raised an estimator error. | Read the event `detail.message` and the run traceback if the stage failed. |
| `baseline_gate_not_met` | Non-baseline sections were skipped because baseline-with-controls was not significant in the expected direction. | Review the baseline candidate row before interpreting missing robustness or mechanism cells. |

## Python Estimator Limitation

The Python estimator backend is `pyfixest`.

If a model is not supported by `pyfixest`, fail clearly rather than adding an ad-hoc fallback.
