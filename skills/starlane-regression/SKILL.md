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

Follow `references/workflow.md`:

1. Profile the data with `uv run python scripts/workflow/profile_data.py ...`.
2. Explain the inference boundary from `references/agent-language-style.md`.
3. Initialize one `analysis_plan_draft`.
4. Confirm each model module and write decisions into that same draft.
5. Render a human-readable review of the same draft.
6. Save or state the confirmed plan.
7. Compile the plan to regression args with `uv run python scripts/workflow/compile_plan_to_regression_args.py ...`.
8. Continue to the summary/final env workflow.

The review step is not a second planning phase. It is only a readable rendering of the same `analysis_plan_draft`.

### Direct Execution Mode

Use this mode when the user has already provided complete variable mappings or a regression-compatible argument list.

Validate the inputs, then run the selected env.

Even in direct mode, explain important fields in research language when reporting back to the user.

## Language Rules

Use research-language labels when speaking with the user.

Do not say:

```text
x: Attention 对吗？
```

Say:

```text
基准回归里，核心解释变量选择 Attention，可以吗？
```

Do not say:

```text
meds: Charge|Subsidy|lnCSR 对吗？
```

Say:

```text
机制检验里，机制变量选择 Charge、Subsidy、lnCSR，可以吗？
```

Before suggesting variable roles, say:

```text
我先根据数据里的列名和基本结构做一个初步判断。因为变量名是你在数据中命名的，我只能从名称、类型、缺失情况和常见经管研究习惯推断变量角色，不能保证理解完全正确；如果某个变量的实际含义和我的推断不一致，以你的解释为准。
```

Regression field names may appear in reproducibility notes, generated source explanations, and regression args. They should not be the primary wording for user confirmation.

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

## Summary Stage

The summary stage searches supported combinations and writes:

```text
.starlane/combination_summary.csv
```

The summary table is an intermediate decision artifact. Do not treat the highest score as automatic final selection.

Before large summary runs, estimate and explain the rough workload:

```text
valid control subsets * 4 VCE choices * model specifications
```

## Model Selection, Ethics, And Boundaries

Starlane is a reproducible empirical-analysis workflow, not a significance factory.

Scoring in `combination_summary.csv` is a search aid. It helps sort candidate models, but it is not proof that the highest-scoring model is the best research design.

When recommending or selecting a model, consider:

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

The final stage uses the selected row from `combination_summary.csv`.

It must output:

- exact source code used to produce the result
- Word regression output produced by running the generated source when the env runtime is available
- env-specific run note or log
- reproducibility note

## Required Deliverables

- data profile when guided setup mode is used
- confirmed `analysis_plan` or a clear direct-mode variable mapping
- compiled regression args or equivalent reproducibility record
- `.starlane/combination_summary.csv`
- user-selected candidate row or explicitly delegated model-selection choice
- exact source code used for final execution (`.py` for Python env or `.do` for Stata env)
- Word regression output when the generated source executes successfully
- env-specific logs or run notes
- short model-selection explanation
- short reproducibility note
- limitations and unsupported-causal-language warnings when relevant
