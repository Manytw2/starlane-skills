---
name: starlane-regression
description: Use when the user has data and variable mappings and wants to run Starlane's supported regression delivery workflow. Python and Stata are selectable execution backends. If the user does not specify a backend, ask them to choose before running. The workflow first produces a combination summary table, then waits for the user to choose a candidate row, then produces the final regression output and exact source code used. Supports baseline regressions, control-variable/VCE search, supported robustness checks, IV, mediation, moderation, and discrete-group heterogeneity as defined in this skill's references. Do not use for DID, RDD, PSM, SCM, DML, event studies, or methods outside the current contract.
---

Run Starlane's first-version two-stage regression delivery workflow.

## Read First

Before taking action, read:

- `references/user-data-and-io-contract.md`
- `references/empirical-section-schema.md`
- `references/supported-methods.md`
- `references/workflow-contract.md`
- `references/troubleshooting.md`

## Scope

Use this skill only when the user already has data and can provide variable roles.

Do not invent variables, data sources, identification strategies, or unsupported methods.

## Nature

This skill is a regression delivery workflow.

Python and Stata are selectable execution backends. They are implementation languages, not separate workflows.

If the user has not selected a backend, ask them to choose before running.

Do not switch backend mid-workflow unless the user asks.

## Workflow

1. Confirm the request is inside `references/supported-methods.md`.
2. Collect and validate the required fields in `references/user-data-and-io-contract.md`.
3. Confirm the execution backend: Python or Stata. If unspecified, ask the user before running.
4. Run the summary stage with the selected backend.
5. Deliver `.starlane/combination_summary.csv` and explain how to choose a candidate row.
6. Ask the user to choose one candidate row from the summary table, unless they explicitly delegated model selection.
7. Generate the selected backend's final source artifact for the selected row.
8. Run the generated final source artifact when the backend runtime is available.
9. Deliver the generated source artifact, Word output, model-selection explanation, limitations, and reproduction notes.

## Backends

Supported backends:

- Python: always run project Python scripts through `uv run python ...` and output `.py` source.
- Stata: use generated or provided `.do` code and output `.do` source.

Do not switch backend mid-workflow unless the user asks.

If the selected backend cannot be executed in the local environment, still generate the source artifact when possible and clearly state that execution was not completed.

Current backend entrypoints:

- Python summary: `uv run python scripts/regression_summary.py ...`
- Python final source generator: `uv run python scripts/generate_regression_py.py ...`
- Python generated final runner: `uv run python regression_generated.py`
- Python generated final runner support: `scripts/regression_final.py`
- Stata summary: `scripts/regression_summary.do`
- Stata final source generator: `scripts/generate_regression_do.py`

Current Python backend scope follows the same section families as the Stata backend: baseline, supported robustness checks, IV, mediation, moderation, discrete heterogeneity, control-variable subset search, VCE enumeration, and selected-row final output. Do not claim numerical parity with Stata `reghdfe`/`ivreghdfe` until cross-backend tests prove it for the relevant section and VCE type.

Implementation-quality note: the current Python backend is a runnable workflow backend, not the final econometrics-quality backend. Its internal estimator exists to keep the three-stage contract executable. The production Python backend target is `pyfixest`; do not add a second estimation fallback. The Word output only needs to follow Starlane's standard report-table format, not `reg2docx` byte-for-byte layout.

## Summary Stage

The summary stage searches supported combinations and writes:

```text
.starlane/combination_summary.csv
```

The summary table is an intermediate decision artifact. Do not treat the highest score as automatic final selection.

## Model Selection, Ethics, and Boundaries

Starlane is a reproducible empirical-analysis workflow, not a significance factory.

Scoring in `combination_summary.csv` is a search aid. It helps sort candidate models, but it is not proof that the highest-scoring model is the best research design.

Do not blindly choose the highest score. When recommending or selecting a model, consider:

- score rank
- expected coefficient direction
- significance level
- whether robustness checks point in the same direction
- whether selected controls are theoretically reasonable
- whether the VCE choice is defensible
- sample size and missingness
- whether the result looks overfit or fragile

Agents using this skill must:

- keep variable mappings explicit
- explain model-selection criteria in plain language
- preserve generated code and outputs so the result can be reproduced
- distinguish statistical association from causal identification
- flag fragile results, small samples, high missingness, unclear variable definitions, and unsupported causal language
- avoid promising significance, thesis approval, publication, or correctness beyond the data and model contract

## Final Stage

The final stage uses the user-selected row from `combination_summary.csv`.

It must output:

- exact source code used to produce the result
- Word regression output produced by running the generated source when the backend runtime is available
- backend-specific run note or log
- reproducibility note

## Required Deliverables

- `.starlane/combination_summary.csv`
- user-selected candidate row or explicitly delegated model-selection choice
- exact source code used for final execution (`.py` for Python backend or `.do` for Stata backend)
- Word regression output when the generated source executes successfully
- backend-specific logs or run notes
- short model-selection explanation
- short reproducibility note
- limitations and unsupported-causal-language warnings when relevant
