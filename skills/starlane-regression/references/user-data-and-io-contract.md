# User Data And IO Contract

This is the input/output contract for the `starlane-regression` skill.

The skill receives:

- A user-provided data file.
- Explicit variable-role mappings.

It must not infer research roles from variable names, invent variables, or extend the workflow to unsupported methods.

## Required Inputs

| Field | Format | Meaning |
| --- | --- | --- |
| `input_dta` | file path | Input data file. Supported: `.dta`, `.xlsx`, `.xls`, `.csv`. |
| `y` | space-separated | Dependent variables. |
| `x` | space-separated | Core independent variables. |
| `cv` | space-separated | Full control-variable pool. |
| `panelvar` | single variable | Panel entity variable, such as `id` or `firm_id`. |
| `timevar` | single variable | Time variable, such as `year`. |

Stop before running if any required input is missing.

## Optional Inputs

| Field | Format | Default | Meaning |
| --- | --- | --- | --- |
| `cv_fixed` | space-separated | empty | Controls that must appear in every subset. Must be a subset of `cv`. |
| `cv_min_count` | integer | `0` | Minimum number of controls in each valid subset. |
| `rob_vars` | `type:value|type:value` | empty | Robustness-variable configuration. |
| `y_ln` | boolean-like string | enabled | Whether to run log-Y robustness for original `y`. |
| `x_ln` | boolean-like string | enabled | Whether to run log-X robustness for original `x`. |
| `rob_year_range` | `left:right` | empty | Robustness sample window, such as `2015:2020`. |
| `iv` | space-separated | empty | Instrumental variables. |
| `meds` | pipe-separated | empty | Mediation or mechanism variables. |
| `mods` | pipe-separated | empty | Moderation variables. |
| `heterogeneity_discrete` | pipe-separated | empty | Discrete heterogeneity grouping variables. |
| `heterogeneity_discrete_values` | `var:v1;v2|var2:v3;v4` | empty | Selected values for each discrete group variable. |
| `coef_direction` | `positive` or `negative` | `positive` | Expected coefficient direction for summary scoring and pruning only. |

## Validation

Before running regressions, validate:

- Data file exists and has a supported format.
- Required fields are non-empty.
- `y`, `x`, `cv`, `panelvar`, and `timevar` variables exist in the data.
- `cv_fixed` is a subset of `cv`.
- `cv_min_count` is a non-negative integer and does not exceed the number of controls.
- `coef_direction` is `positive` or `negative`.
- `rob_vars` types are only `alt_x`, `alt_y`, `ln_x`, `ln_y`, or `lag`.
- `lag` values are positive integers.
- `rob_year_range` parses to a valid interval with left <= right.
- `heterogeneity_discrete_values` keys correspond to variables in `heterogeneity_discrete`.

## Positional Argument Order

When a backend requires positional arguments, use this order:

```text
input_dta
y
x
cv
cv_fixed
cv_min_count
panelvar
timevar
meds
mods
heterogeneity_discrete
heterogeneity_discrete_values
rob_vars
y_ln
x_ln
rob_year_range
iv
coef_direction
```

The final stage appends:

```text
cv_idx
vce_idx
```

## Panel And VCE Mapping

Only pass `panelvar` and `timevar`. The execution layer derives:

```text
cluster_var  = panelvar
cluster_var2 = timevar
```

There is no fallback when either field is missing.

VCE choices are fixed:

| `vce_idx` | `vce_suffix` | Meaning |
| --- | --- | --- |
| `0` | `ols` | Conventional standard errors. |
| `1` | `robust` | Robust standard errors. |
| `2` | `cluster_{panelvar}` | One-way clustered by entity. |
| `3` | `cluster_{panelvar}_{timevar}` | Two-way clustered by entity and time. |

## Control-Variable Search

The summary stage enumerates control-variable subsets:

- `cv` is the full control pool.
- `cv_fixed` variables appear in every subset.
- `cv_fixed` must be a subset of `cv`.
- `cv_min_count` constrains total controls in each subset.
- Each valid subset gets a `cv_idx`.
- Final selection uses `cv_idx + vce_idx`.

Do not use encrypted strings, redeem keys, or passwords to represent model selection.

## Robustness Variables

`rob_vars` format:

```text
type:value|type:value
```

Supported types:

| Type | Example | Meaning |
| --- | --- | --- |
| `alt_x` | `alt_x:x2 x3` | Alternative X variables. |
| `alt_y` | `alt_y:y2 y3` | Alternative Y variables. |
| `ln_x` | `ln_x:x2` | Additional X variables for log robustness. |
| `ln_y` | `ln_y:y2` | Additional Y variables for log robustness. |
| `lag` | `lag:1 2 3` | Lag periods for core X variables. |

For `y_ln` and `x_ln`, empty, `1`, `yes`, `true`, and `是` mean enabled; `0`, `no`, `false`, and `否` mean disabled.

## Discrete Heterogeneity Values

Example:

```text
heterogeneity_discrete = SOE|Region
heterogeneity_discrete_values = SOE:1;0|Region:East;West
```

Rules:

- `:` separates a group variable from its selected values.
- `;` separates values for one variable.
- `|` separates group variables.
- URL-encoded keys and values must be decoded by the parser.
- Output column identifiers must remain stable and parseable when values contain spaces, Chinese text, or special characters.

## Summary Output

The summary stage must output `combination_summary.csv`.

Each row is one `cv_idx + vce_idx` candidate. Fixed columns:

| Column | Meaning |
| --- | --- |
| `selection_id` | Plain identifier: `{cv_idx}_{vce_idx}`. |
| `cv_idx` | Control-subset index. |
| `vce_idx` | VCE index. |
| `vce_suffix` | Human-readable VCE suffix. |
| `cv_selected` | Selected controls joined by `|`; empty subset is an empty string. |
| `score` | Sum of direction-aware significance-star scores across sections. |

Dynamic coefficient columns follow `empirical-section-schema.md`.

Coefficient cells use:

```text
{coef}{stars}
```

Regression failure, insufficient sample, or missing target coefficients leave the cell empty.

Summary output must not contain encrypted selection fields, redeem keys, or passwords.

## Final Output

The final stage consumes:

```text
original inputs + cv_idx + vce_idx
```

It must produce:

| Artifact | Meaning |
| --- | --- |
| Final source | Readable, reproducible `.do` or `.py` source. |
| Result table | Regression output, preferably Word when supported. |
| Run note | Backend, parameters, selected row, and execution status. |
| Reproduction note | How to reproduce the result from the same inputs and selection. |

If Stata, Python dependencies, or Word export dependencies are unavailable, still generate final source when possible and state what could not be executed.
