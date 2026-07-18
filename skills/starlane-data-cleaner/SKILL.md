---
name: starlane-data-cleaner
description: Use when the user wants to clean, reshape, append, merge, or construct analysis datasets for economics or management empirical research. The skill uses a stable Python execution engine and a structured cleaning_plan rather than one-off generated scripts. It profiles input files, executes supported cleaning and merge operations, validates keys, merge results, row flow, missingness, and reproducibility evidence, then guides the user when data-definition or research judgments are required.
---

Build reproducible analysis datasets from raw empirical data.

## Target User

The primary user is an economics or management student or researcher preparing
data for empirical analysis.

The agent is a careful research assistant. It should clarify what the final
analysis dataset should represent, run a parameterized cleaner, inspect the
diagnostics, and guide the user through ambiguous data decisions.

## Read First

Before taking action, read the relevant references.

Always read:

- `references/workflow.md`
- `references/cleaning-plan-schema.md`
- `references/data-quality-rubric.md`
- `references/agent-language-style.md`
- `references/output.md`

When troubleshooting, read:

- `references/troubleshooting.md`

## Scope

Supported workflow:

- input data profiling
- target dataset expectation drafting
- structured `cleaning_plan` creation or revision
- Python execution of supported cleaning and merge operations
- output validation against hard gates and configured thresholds
- human-readable cleaning report generation

Supported first-version operations:

- read `csv`, `xlsx`, `xls`, and `dta`
- rename columns
- select or drop columns
- trim, lowercase, and uppercase string columns
- cast columns to string, integer, float, or date
- left-pad identifier strings
- replace coded missing values
- drop duplicate rows by key with explicit methods
- filter rows with a recorded reason
- append datasets
- merge datasets with `1:1`, `m:1`, or `1:m` expectations
- write `csv` and `dta`

Unsupported unless added to the engine through a development change:

- fuzzy matching
- many-to-many merge as an automatic fix
- external API crosswalks
- arbitrary custom Python or Stata cleaning logic
- automatic imputation
- automatic winsorization or trimming of economically meaningful variables
- silent deletion of unmatched or duplicate observations

## Plan-Run-Diagnose-Revise Loop

This skill uses a stable execution engine and a structured `cleaning_plan`.
The ordinary loop revises the plan, not the engine code.

1. Establish the target dataset expectation: observation unit, target key,
   required variables, expected merge relationships, and known tolerances.
2. Generate or update `cleaning_plan.json` using supported operations.
3. Run the stable cleaner engine with the plan.
4. Inspect diagnostics: output existence, row and column counts, key
   missingness, key uniqueness, merge matched/left-only/right-only counts,
   row-flow losses, critical-variable missingness, impossible values when
   configured, and reproducibility evidence.
5. If a hard expectation fails and the fix is covered by supported operations,
   revise `cleaning_plan.json` and rerun the same engine.
6. If the fix requires a data-definition or research judgment, explain the
   issue, show evidence, present feasible options, recommend one option with
   tradeoffs, and ask the user to confirm before applying it.
7. Do not manually patch output datasets. Do not change engine code during
   ordinary data-cleaning work. Expanding engine capabilities is a development
   task and should be proposed separately.

## Env

The first supported env is Python.

Use the skill-local Python project as the runtime contract:

```text
uv run --project <skill-root> python scripts/workflow/run_stage.py ...
```

Do not rely on the user's current workspace Python environment.

## Commands

Profile input data:

```text
uv run --project <skill-root> python scripts/workflow/run_stage.py profile --inputs-json .starlane/data_cleaner_inputs.json
```

Run the cleaner from a plan:

```text
uv run --project <skill-root> python scripts/workflow/run_stage.py run --plan .starlane/cleaning_plan.json
```

Validate an existing output from a plan:

```text
uv run --project <skill-root> python scripts/workflow/run_stage.py validate --plan .starlane/cleaning_plan.json --data output/starlane-data-cleaner/python/analysis_data.csv
```

## Required Deliverables

- target dataset expectation or explicit assumptions
- `cleaning_plan.json`
- user-facing analysis dataset
- `cleaning_diagnostics.json`
- `cleaning_report.md`
- a short explanation of hard gate failures or pass status
- guided recommendation for any unresolved data-definition decision

## Boundaries

Do not describe a completed run as successful unless diagnostics satisfy the
stated expectation.

Do not treat higher row counts, lower missingness, or higher match rates as
automatically better. They must be consistent with the expected observation
unit, key, source data, and research purpose.

Large sample loss is not automatically wrong, but it is never silent.
