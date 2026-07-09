# Workflow

`starlane-regression` implements one regression delivery workflow with multiple envs.

It guides undergraduate economics and management students from data to a reproducible Starlane regression run without asking them to directly fill regression parameters.

```text
user data + variable mapping
-> initialize or validate analysis_plan
-> choose env: Python or Stata
-> compile regression args
-> summary stage
-> combination_summary.csv
-> choose cv_idx and vce_idx
-> final source generation
-> generated source artifact for the selected env
-> run generated source artifact when possible
-> regression output
-> Agent explains reproducibility from runtime evidence when relevant
```

Python and Stata are envs, not separate user workflows.

If the user has not selected an env, ask before running.

## Entry Modes

Guided setup mode starts from a data file, partial variables, or a research idea.

Direct execution mode starts from complete variable mappings or a valid structured `regression_args.json`.

In guided setup mode, do not ask the user to directly fill regression args. Maintain one `analysis_plan_draft`, confirm each model module into that draft, then compile the confirmed plan.

In direct execution mode, validate the supplied inputs, choose the env, then run the shared execution flow.

## One Plan Draft

The agent must maintain one `analysis_plan_draft` throughout guided setup.

Do not run:

```text
module guidance -> separate plan drafting -> regression args
```

Run:

```text
data profile -> initialize analysis_plan_draft -> confirm each model module into that same draft -> review draft -> compile regression args -> execute
```

The final review is a human-readable view of the same draft, not a second planning phase.

## Guided Setup Flow

1. Read the data and generate a data profile.
2. Explain the inference boundary from `agent-language-style.md`.
3. Initialize `analysis_plan_draft.data`.
4. Confirm the research main line.
5. Confirm baseline regression.
6. Confirm robustness checks.
7. Confirm mechanism or mediation checks.
8. Confirm moderation checks.
9. Confirm heterogeneity checks.
10. Confirm IV checks.
11. Render the same draft for review.
12. Save the confirmed plan.
13. Compile regression args.
14. Run the shared execution flow.

## Module Rhythm

Each module uses this rhythm:

1. Explain what question this model answers.
2. List data-derived candidate variables.
3. Give the agent's recommendation.
4. Ask the user to confirm or modify in research language.
5. Write the confirmed decision into the corresponding `analysis_plan_draft` section.
6. Continue to the next module.

## Default Module Policy

| Module | Default behavior |
| --- | --- |
| Baseline | Required and enabled |
| Robustness | Recommended when candidate variables or lags exist |
| Mechanism or mediation | Recommended when plausible path variables exist |
| Moderation | Recommended when plausible condition variables exist |
| Heterogeneity | Ask; do not silently enable |
| IV | Discuss as an extension; do not silently promote to main identification |

## Candidate Suggestions

The agent may suggest candidate roles from:

- variable names
- missingness
- data type
- unique counts
- common economics and management conventions
- panel structure

The agent must treat these as hypotheses, not facts.

## Review Before Execution

Before execution, show a compact human-readable review:

```text
基准回归:
- 被解释变量: ...
- 核心解释变量: ...
- 控制变量: ...

稳健性检验:
- ...

机制检验:
- ...
```

Then compile the same plan draft. Do not ask the user to restate regression parameters.

## Shared Execution Flow

After guided setup or direct validation, run:

```text
analysis_plan or direct mapping
-> compile regression args
-> selected env summary stage
-> combination_summary.csv
-> choose cv_idx and vce_idx
-> selected env final stage
-> generated source artifact
-> run generated source artifact when possible
-> regression output
-> Agent explains reproducibility from runtime evidence when relevant
```

## Shared Env Requirements

Envs must share:

- `analysis_plan` schema
- supported model families
- module section structure
- summary/final stage contract
- candidate selection identifiers
- deliverable checklist
- research-language explanation boundaries

Current Python and Stata env scope follows the same section families:

- baseline
- supported robustness checks
- IV
- mediation
- moderation
- discrete heterogeneity
- control-variable subset search
- VCE enumeration
- selected-row final output

## Env Differences

Envs may differ in:

- estimator package and defaults
- fixed-effect absorption implementation
- standard-error corrections
- missing-data behavior when package defaults differ
- generated source-code shape
- Word/table rendering implementation
- runtime and dependency notes

Do not force one env to mimic the other. Each env should follow publication-grade conventions in its own ecosystem and disclose runtime, packages, versions, and estimation choices.

## No Cross-Env Numerical Parity Goal

Envs are not required to produce coefficient-by-coefficient identical results. The goal is:

```text
same workflow
same analysis plan
same module section structure
env-appropriate publication-grade source and reproducibility artifacts
clear disclosure of estimation choices
```

Differences may arise from env-specific estimator implementations, degrees-of-freedom corrections, fixed-effect absorption, clustering, missing-data handling, and package defaults.

## Module Contract Rules

Each supported module file in `references/models/` defines its own user guidance, analysis plan fields, section schema, regression args contribution, and interpretation boundaries.

Module section schemas must follow these rules:

- Column segments use `__`.
- Section enablement, expansion dimensions, and loop order must be stable.
- Summary-stage dynamic columns and final-stage model blocks must be isomorphic.
- All envs use the same module section structure.

## Candidate Selection

The summary stage enumerates control-variable subsets and VCE choices.

- `cv_idx` identifies one valid control-variable subset.
- `vce_idx` identifies one VCE choice.
- Final selection uses the same `cv_idx + vce_idx` pair from the current `combination_summary.csv`.

Each row in `combination_summary.csv` is a candidate setting, not a single
model. A candidate setting contains:

- one shared control-variable combination identified by `cv_idx`
- one VCE choice identified by `vce_idx`
- the results for all enabled model sections under that same control-variable
  combination and VCE choice

Do not describe the workflow as if baseline, robustness, mechanism,
moderation, heterogeneity, or IV sections independently choose different
control-variable combinations inside the same candidate row.

Before large summary runs, estimate workload in terms of:

```text
candidate control-variable combinations * 4 VCE choices * enabled model-section regressions
```

Explain the concrete recommended control setting and workload to the user. Do
not expose internal control-count heuristics as something the user needs to
understand before continuing.

VCE choices are fixed:

| `vce_idx` | `vce_suffix` | Meaning |
| --- | --- | --- |
| `0` | `ols` | Conventional standard errors. |
| `1` | `robust` | Robust standard errors. |
| `2` | `cluster_{panelvar}` | One-way clustered by entity. |
| `3` | `cluster_{panelvar}_{timevar}` | Two-way clustered by entity and time. |

`combination_summary.csv` fixed columns:

| Column | Meaning |
| --- | --- |
| `selection_id` | Plain identifier: `{cv_idx}_{vce_idx}`. |
| `cv_idx` | Control-subset index. |
| `vce_idx` | VCE index. |
| `vce_suffix` | Human-readable VCE suffix. |
| `cv_selected` | Selected controls joined by `|`; empty subset is an empty string. |
| `score` | Sum of direction-aware significance-star scores across module sections. |

Dynamic coefficient columns are defined by the section schemas in `references/models/`.

Final source generation consumes the compiled regression args JSON plus a `selected_candidate.json` object containing `cv_idx` and `vce_idx`.

## Output And Runtime Directories

User-facing outputs are published per env:

```text
output/starlane-regression/
├── python/
│   ├── combination_summary.csv
│   ├── final_result.csv
│   ├── final_result.md
│   ├── final_result.docx
│   └── regression_generated.py
└── stata/
    ├── combination_summary.csv
    ├── regression_generated.do
    └── starlane-regression-results.docx
```

Internal run evidence is written under the ignored runtime directory:

```text
.starlane/runtime/starlane-regression/runs/<run-id>/
├── inputs/
├── generated/
├── logs/
├── outputs/
├── tmp/
└── run.json
```

Env scripts do not manage the full runtime lifecycle. They write outputs to
`STARLANE_EXPORT` and temporary files to `STARLANE_TMP`. The outer runner
(`scripts/workflow/run_stage.py`) creates the run directory, sets those paths,
collects logs, updates `run.json`, verifies the summary header against the
canonical ModelPlan, publishes user-facing outputs on success, and cleans
`tmp/` after successful runs.

Chunked summary runs (`--cv-idx-start/--cv-idx-end`) produce partial tables.
They stay in the run's `outputs/` directory and are not published.

Stata env can override these paths by setting globals before running `scripts/envs/stata/summary.do`:

```stata
global STARLANE_EXPORT "/path/to/export"
global STARLANE_TMP "/path/to/export/tmp"
```
