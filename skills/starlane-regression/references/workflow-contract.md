# Workflow Contract

`starlane-regression` implements one two-stage regression delivery workflow:

```text
user data + variable mapping
-> choose backend: Python or Stata
-> summary stage
-> combination_summary.csv
-> choose cv_idx and vce_idx
-> final source generation
-> generated source artifact for the selected backend
-> run generated source artifact when possible
-> regression output
-> reproducibility notes
```

Python and Stata are selectable execution backends. They are implementation languages, not separate workflows.

If the user has not selected a backend, ask before running.

## Backend Mapping

Stata backend:

```text
summary stage -> scripts/regression_summary.do
final stage -> scripts/generate_regression_do.py -> generated .do -> optional Stata execution
```

Python backend:

```text
summary stage -> uv run python scripts/regression_summary.py
final stage -> uv run python scripts/generate_regression_py.py -> generated .py -> uv run python regression_generated.py
```

Python scripts in this project must be invoked through:

```text
uv run python ...
```

Do not run project workflow scripts with bare `python`, `python3`, or executable shebangs in agent instructions, generated run notes, or tests.

## Python Backend Status

Current Python backend scope follows the same section families as Stata:

- baseline
- supported robustness checks
- IV
- mediation
- moderation
- discrete heterogeneity
- control-variable subset search
- VCE enumeration
- selected-row final output

It does not claim numerical parity with Stata `reghdfe`/`ivreghdfe`.

The Python estimator/output implementation is not final. The production Python backend target is `pyfixest`. Do not add a second estimation fallback. If `pyfixest` cannot cover a required model, fail clearly and update the contract rather than silently switching libraries.

## Chunked Summary Runs

Chunked test runs are not full enumeration.

If `cv_idx_start` and `cv_idx_end` are provided, the summary stage only evaluates that inclusive control-subset range.

Full enumeration count is:

```text
valid control-variable subsets * 4 VCE choices
```

## Default Output Directory

By default, the skill writes:

```text
.starlane/
├── combination_summary.csv
└── tmp/
```

Stata backend can override these paths by setting globals before running `regression_summary.do`:

```stata
global STARLANE_EXPORT "/path/to/export"
global STARLANE_TMP "/path/to/export/tmp"
```
