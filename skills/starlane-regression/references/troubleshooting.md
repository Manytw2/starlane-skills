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

- `uv` is unavailable: install or activate `uv`, or run from an environment where project scripts can be invoked through `uv run python`.
- Data import fails: confirm the file extension is `.dta`, `.csv`, `.xlsx`, or `.xls`; for `.dta`, confirm `pyreadstat`/pandas support the file.
- Missing dependency: confirm `numpy`, `pandas`, `pyreadstat`, and `python-docx` are installed through the project environment.
- Word export fails: confirm `python-docx` is installed and the output path is writable.
- Generated source runs in the wrong directory: run it from the skill directory or use absolute paths in the generated source.
- Summary succeeds but final fails: confirm the final args use the same 18 base arguments and a `cv_idx`/`vce_idx` from the same `combination_summary.csv`.

## Stata Target Issues

Common Stata errors:

- `r(601)`: input file path is wrong or Stata cannot access the file.
- `r(111)`: a mapped variable does not exist.
- `r(109)`: a numeric operation was applied to a string variable.
- `r(198)`: argument order, quoting, or option value is invalid.

Missing packages:

- `reghdfe` missing: run `ssc install reghdfe`.
- `ivreghdfe` missing: run `ssc install ivreghdfe`.
- `reg2docx` or `sum2docx` missing: install the required Stata export package before running the generated final `.do`.

## Summary-Final Selection Issues

If summary generation succeeds but final generation fails, check that:

- the same confirmed analysis plan or same 18 compiled arguments were reused
- `cv_idx` and `vce_idx` came from the same `combination_summary.csv`
- the selected env is the same env intended for final source generation
- the generated source file points to a writable output path

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

## Python Estimator Limitation

The current Python estimator is not the final publication-grade econometrics env.

If a model is not supported by the selected mature Python econometrics package, fail clearly rather than adding an ad-hoc fallback.
