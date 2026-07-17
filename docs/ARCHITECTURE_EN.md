# Starlane Skills Architecture

This document explains the current structure and main design choices of Starlane Skills. It is written for contributors and maintainers, not as an end-user tutorial.

## Project Positioning

Starlane Skills is not a collection of standalone scripts. It is a set of Agent-guided empirical-analysis workflows.

The current production entrypoints are:

```text
skills/starlane-regression/SKILL.md
skills/starlane-data-cleaner/SKILL.md
```

A user can start from a data file, partial variable mappings, or a research idea. The Agent first turns the research setup into one `analysis_plan`, then compiles that plan into executable regression arguments, and finally runs the summary and final stages through a selected Python or Stata environment.

Data cleaning and merging tasks enter through `starlane-data-cleaner`. The Agent first confirms the target analysis dataset's observation unit, keys, required variables, and merge relationships, then generates or revises a `cleaning_plan` for the stable Python engine to clean, merge, diagnose, and report.

## Core Principles

### One User Entrypoint

The first version does not split the workflow into multiple skills such as `starlane-baseline`, `starlane-robustness`, or `starlane-iv`.

For users, empirical analysis is one continuous workflow: clarify the research line, confirm the baseline model, then decide whether robustness checks, mechanisms, moderation, heterogeneity, or IV-style checks are appropriate. Multiple user-facing entrypoints would expose implementation boundaries too early and make it harder for the Agent to maintain one research plan.

### One Analysis Plan

In guided setup mode, the Agent maintains one `analysis_plan_draft`.

The intended flow is:

```text
data profile -> initialize analysis_plan_draft -> confirm modules -> review the same draft -> compile regression args -> execute
```

The flow should not be:

```text
module discussion -> separate natural-language plan -> separate structured plan -> execute
```

`analysis_plan` is the research-layer representation. Regression arguments are the execution-layer representation. When confirming choices with the user, the Agent should use research language such as outcome variable, explanatory variable, mechanism variable, or fixed effects instead of asking the user to fill backend fields such as `y`, `x`, or `meds`.

### Python and Stata Are Environments

Python and Stata are execution environments, not separate user workflows.

They share:

- the `analysis_plan` schema
- supported model modules
- the summary / final stage contract
- candidate-setting selection identifiers
- the deliverable checklist
- research-language and interpretation boundaries

They may differ in:

- estimator packages and defaults
- fixed-effect absorption
- standard-error corrections
- package-level missing-data behavior
- generated source-code shape
- table export mechanisms
- runtime, dependency, and log evidence

The project does not require Python and Stata to produce coefficient-by-coefficient identical results. The goal is the same workflow, the same research plan, environment-appropriate reproducible source code, and clear disclosure of estimation choices.

### Cleaning Loops Revise Plans, Not Engines

The ordinary `starlane-data-cleaner` loop is:

```text
profile -> cleaning_plan -> run -> diagnostics -> revise cleaning_plan -> rerun
```

The AI understands the goal, generates or revises `cleaning_plan`, explains diagnostics, and recommends parameter choices. The stable engine interprets the plan, runs supported cleaning and merge operations, writes data, and writes diagnostics. Ordinary cleaning tasks do not patch engine code or manually edit output datasets. Missing engine capabilities should be proposed as development work.

## Workflow

```text
user data or variable mappings
-> generate data profile
-> explain variable-inference boundaries
-> initialize analysis_plan_draft
-> confirm research line and model modules
-> review the same analysis_plan_draft
-> save the confirmed analysis_plan
-> compile regression args
-> summary stage writes combination_summary.csv
-> user selects or confirms a candidate setting
-> final stage writes final output and source code
```

The summary stage enumerates candidate settings. Each candidate setting contains one shared control-variable combination, one standard-error choice, and all enabled model-section results under that setting. The resulting `combination_summary.csv` is a decision aid, not an automatic final conclusion.

The final stage uses the selected candidate row to generate final regression output and reproducible source code. Generated sources in both envs (`.py` / `.do`) must be self-contained: all regression specs are expanded at generation time, and the file depends only on public packages in its own ecosystem (pyfixest/python-docx or reghdfe/reg2docx), never on scripts inside this repository.

## Key Contracts

### `analysis_plan`

`analysis_plan` is organized by research module and represents the user's confirmed research setup. It commonly includes:

```text
data
research
baseline
robustness
mechanism
moderation
heterogeneity
iv
execution
```

See the full schema:

```text
skills/starlane-regression/references/analysis-plan-schema.md
```

### Regression Args

Regression args are the execution-layer parameter contract compiled from `analysis_plan`. They are not the primary user-facing interaction model.

Compiler entrypoint:

```text
uv run --project skills/starlane-regression python skills/starlane-regression/scripts/workflow/run_stage.py compile ...
```

### `cleaning_plan`

`cleaning_plan` is the execution-layer contract for `starlane-data-cleaner`. It describes the target dataset, input files, parameterized cleaning and merge operations, validation thresholds, and output location.

The ordinary loop revises only `cleaning_plan`:

```text
skills/starlane-data-cleaner/references/cleaning-plan-schema.md
```

Runner entrypoint:

```text
uv run --project skills/starlane-data-cleaner python skills/starlane-data-cleaner/scripts/workflow/run_stage.py run --plan ...
```

### Candidate Setting Selection

The summary stage writes:

```text
output/starlane-regression/<env>/combination_summary.csv
```

Important columns:

- `selection_id` is a plain candidate identifier.
- `cv_idx` identifies the control-variable subset.
- `vce_idx` identifies the standard-error choice.
- `cv_selected` records the selected controls.
- `score` is a direction-aware significance aid.

`score` can help with sorting and inspection. It must not replace research judgment.

### Runtime and Output Layout

Starlane separates user-facing outputs from internal run evidence:

```text
output/starlane-regression/
  python/
    combination_summary.csv
    final_result.docx
    generated_regression.py
    ...
  stata/
    combination_summary.csv
    generated_regression.do
    final_result.docx

output/starlane-data-cleaner/
  python/
    analysis_data.csv
    cleaning_plan.json
    cleaning_diagnostics.json
    cleaning_report.md

.starlane/runtime/starlane-regression/runs/<run-id>/
  inputs/
  generated/
  logs/
  outputs/
  tmp/
  run.json
```

`output/starlane-regression/<env>/` is the user-facing result location; per-env directories keep same-named artifacts from overwriting each other. `.starlane/runtime/` is the ignored internal directory for Agent and maintainer diagnostics.

`output/starlane-data-cleaner/python/` is the data-cleaner user-facing output location. The first data-cleaner implementation keeps runtime lightweight: reproducibility fields are written into diagnostics, and the final plan is copied into public output.

Python and Stata envs only execute summary/final logic. The orchestration entrypoint `scripts/workflow/run_stage.py` creates run directories, writes manifests, sets `STARLANE_EXPORT` and `STARLANE_TMP`, verifies the summary header against the canonical ModelPlan, publishes public outputs on success, and cleans `tmp/` after successful runs. Chunked summary runs (`--cv-idx-start/--cv-idx-end`) are intermediate artifacts and are not published.

The summary stage is orchestrated by `scripts/workflow/summary_parallel.py`: it picks a concurrency level from machine cores, available memory, and task count, splits the cv-subset range into guided self-scheduling chunks (decreasing sizes), runs multiple `build_summary.py --cv-idx-start/end` subprocesses for the Python env or multiple `stata -b` batch instances for the Stata env, then merges the part tables, checks `selection_id` uniqueness, and writes `combination_summary.csv` sorted by `score` descending. Serial execution is just the concurrency-1 degenerate case; there is no separate code path. Two concurrency rules apply: each Stata worker gets its own `STATATMP` subdirectory (concurrent instances sharing a temp dir overwrite each other's preserve/tempfile state), and each Python worker caps BLAS/numba threads at 1 to avoid thread oversubscription on top of process-level parallelism. xlsx/xls inputs are warmed into a cache once (`.dta` for Stata, `.pkl` for Python) so workers do not re-parse slow formats.

Successful runs do not retain low-value intermediates such as `.score_*.dta`. Failed runs keep logs and tmp files for diagnosis.

## Directory Structure

```text
skills/starlane-regression/
  SKILL.md
  references/
    workflow.md
    agent-language-style.md
    analysis-plan-schema.md
    supported-methods.md
    output.md
    troubleshooting.md
    models/
      baseline.md
      robustness.md
      mechanism.md
      moderation.md
      heterogeneity.md
      iv.md
  scripts/
    workflow/
      run_stage.py
      summary_parallel.py
      contracts.py
      model_plan.py
      stata_config.py
      plan_drift_check.py
      profile_data.py
      compile_plan.py
      runtime.py
    envs/
      python/
      stata/

skills/starlane-data-cleaner/
  SKILL.md
  references/
    workflow.md
    cleaning-plan-schema.md
    data-quality-rubric.md
    agent-language-style.md
    output.md
    troubleshooting.md
  scripts/
    workflow/
      run_stage.py
      profile_data.py
      execute_plan.py
      validate_output.py
      contracts.py
      report.py
      runtime.py
    envs/
      python/
```

Responsibilities:

- `SKILL.md`: Agent entrypoint, scope, required references, and boundaries.
- `references/workflow.md`: shared workflow and environment contracts.
- `references/agent-language-style.md`: user-facing language and variable-inference boundaries.
- `references/analysis-plan-schema.md`: analysis-plan structure.
- `references/models/`: model-module guidance, plan fields, section schemas, and interpretation boundaries.
- `references/output.md`: deliverables and table-output rules.
- `references/troubleshooting.md`: common failure modes and recovery guidance.
- `scripts/workflow/run_stage.py`: unified orchestration entrypoint for the profile/compile/summary/final stages and publishing.
- `scripts/workflow/summary_parallel.py`: chunked parallel orchestration for the summary stage (concurrency probing, guided chunking, worker process pool, part merge and sorting).
- `scripts/workflow/contracts.py`: JSON contract validation for regression args and candidate selection.
- `scripts/workflow/model_plan.py`: the single source of truth for model enumeration; answers "what should run".
- `scripts/workflow/stata_config.py`: renders the ModelPlan into Stata configuration.
- `scripts/workflow/plan_drift_check.py`: verifies summary artifacts against the canonical ModelPlan.
- Remaining `scripts/workflow/` files: data profiling, plan compilation, and runtime lifecycle management.
- `scripts/envs/`: Python / Stata summary, final, and source-generation logic; answers "how this env runs it".

`starlane-data-cleaner` responsibilities:

- `SKILL.md`: Agent entrypoint, plan-run-diagnose-revise loop, scope, and judgment boundaries.
- `references/cleaning-plan-schema.md`: `cleaning_plan` parameter contract.
- `references/data-quality-rubric.md`: hard gates, diagnostic metrics, and user-judgment cases.
- `scripts/workflow/run_stage.py`: unified profile/run/validate entrypoint.
- `scripts/workflow/execute_plan.py`: stable plan executor for supported cleaning and merge operations.
- `scripts/workflow/profile_data.py`: input data profiling.
- `scripts/workflow/validate_output.py`: key, missingness, and required-column diagnostics for existing outputs.
- `scripts/workflow/report.py`: human-readable report rendering from diagnostics.

Two auxiliary top-level directories:

- `quick-start/`: demo data and a thin launcher that reuses the `run_stage.py` pipeline.
- `scripts/` (repository root): runtime cleanup and status helpers, plus `stata-code-examples/` (human-facing example code; agents must not use it as workflow input).

## Design Choices

### Still No `_shared` Layer

The project currently has two stable skills: `starlane-regression` and `starlane-data-cleaner`. They share a few concepts such as profile, runtime, and output, but their contracts and user mental models remain different: regression centers on `analysis_plan` and candidate settings, while data cleaning centers on `cleaning_plan` and data-quality diagnostics. Keep code skill-local until real duplication creates a stable reuse boundary.

### Entrypoints Organized by Responsibility

Execution entrypoints are organized by responsibility:

```text
scripts/workflow/
scripts/envs/python/
scripts/envs/stata/
```

Agent instructions and tests should use these paths.

### Significance Is Not the Objective Function

Starlane enumerates model combinations and provides scoring aids, but it is not a significance factory.

Model selection should consider theoretical fit, variable definitions, sample size, missingness, standard-error choices, robustness direction, and interpretation boundaries. The Agent must preserve reproducibility artifacts and distinguish statistical association from causal identification.
