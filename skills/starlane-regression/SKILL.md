---
name: starlane-regression
description: Use when the user wants Starlane's supported regression workflow for economics or management empirical analysis. Supports guided setup from a data file for undergraduate users, or direct execution from complete variable mappings. Python and Stata are selectable envs, not separate workflows. The workflow builds one analysis_plan draft through model-by-model guidance, compiles it to regression arguments, runs a combination summary table, asks for or recommends a candidate row, then produces final regression output and exact source code. Supports baseline regressions, control-variable/VCE search, supported robustness checks, IV, mechanism/mediation checks, moderation, and discrete-group heterogeneity as defined in this skill's references. Do not use for DID, RDD, PSM, SCM, DML, event studies, or methods outside the current contract.
---

Run Starlane's guided regression delivery workflow.

## Target User

The primary user is an undergraduate economics or management student.

They may know basic regression but need help deciding whether to include robustness checks, mechanism checks, moderation, heterogeneity, or IV-style checks.

The agent is a research assistant. It should guide and discuss model choices with the user, then translate confirmed decisions into regression parameters.

## Read First

Before taking action, read the relevant references.

Always read:

- `references/supported-methods.md`
- `references/workflow.md`
- `references/agent-language-style.md`
- `references/analysis-plan-schema.md`

When guiding or executing a module, read its module reference:

- baseline: `references/models/baseline.md`
- robustness: `references/models/robustness.md`
- mechanism/mediation: `references/models/mechanism.md`
- moderation: `references/models/moderation.md`
- heterogeneity: `references/models/heterogeneity.md`
- IV: `references/models/iv.md`

When discussing Word/table output, read:

- `references/output.md`

When troubleshooting, read:

- `references/troubleshooting.md`

## Scope

Supported workflow:

- data profiling
- guided model setup
- one `analysis_plan` draft maintained throughout the conversation
- compilation to regression arguments
- summary table generation
- selected-row final output generation

Unsupported methods remain outside this skill:

- DID
- event study
- RDD
- PSM
- SCM
- DML
- causal forest
- Bayesian models
- survival analysis
- Oaxaca decomposition
- quantile treatment effects

Do not invent variables, data sources, identification strategies, or unsupported methods.

## Two Entry Modes

### Guided Setup Mode

Use this mode when the user provides only a data file, partial variables, or a research idea.

Do not ask the user to directly fill regression args.

Follow these steps, using the module rhythm and default module policy from `references/workflow.md`:

1. Profile the data with `uv run --project <skill-root> python scripts/workflow/run_stage.py profile ...`.
2. Explain the inference boundary from `references/agent-language-style.md`.
3. Initialize one `analysis_plan_draft`.
4. Confirm the research main line, then each model module in order — baseline, robustness, mechanism/mediation, moderation, heterogeneity, IV — writing each confirmed decision into that same draft.
5. Render a human-readable review of the same draft.
6. Save or state the confirmed plan.
7. Compile the plan to regression args with `uv run --project <skill-root> python scripts/workflow/run_stage.py compile ...`.
8. Continue to the summary/final env workflow.

The review step is not a second planning phase. It is only a readable rendering of the same `analysis_plan_draft`.

### Direct Execution Mode

Use this mode when the user has already provided complete variable mappings or a valid structured `regression_args.json`.

Validate the inputs, then run the selected env.

Even in direct mode, explain important fields in research language when reporting back to the user.

## Analysis Plan

In guided setup mode, maintain one `analysis_plan_draft` grouped by model module:

- `data`
- `research`
- `baseline`
- `robustness`
- `mechanism`
- `moderation`
- `heterogeneity`
- `iv`
- `execution`

The final confirmed plan is compiled into regression args consumed by the selected env.

Do not create a separate natural-language plan and then a second structured plan. The structured draft is the source of truth.

## Env

Use the shared workflow rules in `references/workflow.md`.

Supported envs are Python and Stata.

If the user has not selected an env, ask them to choose before running summary/final stages.

Do not switch env mid-workflow unless the user asks.

If the selected env cannot execute locally, still generate the source artifact when possible and clearly state that execution was not completed.

Do not use legacy top-level wrapper paths. New implementation files live under `scripts/workflow/` and `scripts/envs/`.

Use the skill-local Python project as the runtime contract:

```text
uv run --project <skill-root> python scripts/workflow/run_stage.py ...
```

Do not rely on the user's current workspace Python environment.

## Summary Stage

The summary stage searches supported combinations and publishes:

```text
output/starlane-regression/<env>/combination_summary.csv
```

Full runs publish automatically on success and verify the summary header against the canonical ModelPlan. Chunked runs (`--cv-idx-start/--cv-idx-end`) are intermediate artifacts; they stay under the run directory in `.starlane/runtime/` and are not published.

Run summary through JSON files, not positional regression arguments:

```text
uv run --project <skill-root> python scripts/workflow/run_stage.py summary --env python --args-json .starlane/regression_args.json
```

The summary table is an intermediate decision artifact. Do not treat the highest score as automatic final selection.

The summary stage runs control-variable subsets in parallel worker processes when the machine allows. This is internal behavior with no extra flags; the workload decision is printed as a `STARLANE_JOBS:` line, and chunk-level progress events are appended to the run's `logs/progress.jsonl`. Rows in `combination_summary.csv` are sorted by `score` descending in both envs.

Before large summary runs, estimate and explain the rough workload:

```text
candidate control-variable combinations * 4 VCE choices * enabled model-section regressions
```

Explain the concrete recommended control setting and workload to the user in research language. Do not expose internal control-count heuristics as something the user needs to understand before continuing.

## Model Selection, Ethics, And Boundaries

Starlane is a reproducible empirical-analysis workflow, not a significance factory.

Each row in `combination_summary.csv` is a candidate setting: one shared control-variable combination, one VCE choice, and all enabled model-section results under that same setting. Do not describe the workflow as if baseline, robustness, mechanism, moderation, heterogeneity, or IV sections independently choose different control-variable combinations inside the same candidate row.

Scoring in `combination_summary.csv` is a search aid. It helps sort candidate settings, but it is not proof that the highest-scoring setting is the best research design.

When recommending or selecting a candidate setting, consider:

- score rank
- expected coefficient direction
- significance level
- whether robustness checks point in the same direction
- whether selected controls are theoretically reasonable
- whether the VCE choice is defensible
- sample size and missingness
- whether the result looks overfit or fragile

When several candidate settings have the same top score, do not use the first
sorted row as the default recommendation. Actively inspect the tied candidates
and explain the tradeoff before recommending one. Compare at least:

- control-variable count and whether the control set is too sparse for the
  research convention
- whether added controls are theoretically reasonable rather than mechanical
  score padding
- whether a larger control set appears to introduce missingness, sample-size
  loss, unstable estimates, or weaker module performance
- whether the VCE choice remains defensible

In tied-score cases, a moderately richer and theoretically reasonable control
set is often preferable to the sparsest tied setting, but the fullest control
set is not automatically best. Recommend the candidate that best balances
score, conventionally adequate controls, defensible variables, and stability;
name any close alternatives when useful.

Agents using this skill must:

- keep variable mappings explicit
- explain model-selection criteria in plain language
- preserve generated code and outputs so the result can be reproduced
- distinguish statistical association from causal identification
- flag fragile results, small samples, high missingness, unclear variable definitions, and unsupported causal language
- avoid promising significance, thesis approval, publication, or correctness beyond the data and model contract

## Final Stage

The final stage uses the selected row from `combination_summary.csv`.

It must output:

- exact source code used to produce the result
- Word regression output produced by running the generated source when the env runtime is available
- env-specific logs and runtime manifest

## Required Deliverables

- data profile when guided setup mode is used
- confirmed `analysis_plan` or a clear direct-mode variable mapping
- compiled regression args or equivalent reproducibility record
- `output/starlane-regression/<env>/combination_summary.csv`
- user-selected candidate row or explicitly delegated model-selection choice
- exact source code used for final execution (`.py` for Python env or `.do` for Stata env)
- Word regression output when the generated source executes successfully
- env-specific logs and runtime manifest
- short model-selection explanation in the Agent response
- short reproducibility explanation in the Agent response when relevant
- limitations and unsupported-causal-language warnings when relevant
