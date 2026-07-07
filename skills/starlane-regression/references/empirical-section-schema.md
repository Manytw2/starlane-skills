# Empirical Section Schema

This file defines the six empirical-analysis sections supported by `starlane-regression`.

Summary columns, final generated source, and all backends must use this same section schema.

## General Rules

- Column segments use `__`.
- Section enablement, expansion dimensions, and loop order must be stable.
- Summary-stage dynamic columns and final-stage model blocks must be isomorphic.
- Stata and Python backends must represent the same sections.

## 1. Baseline

For each `(y, x)`, run:

- `y ~ x`
- `y ~ x + cv_selected`

Columns:

| Column | Meaning |
| --- | --- |
| `baseline__{y}__{x}__nocv` | No controls; record `x`. |
| `baseline__{y}__{x}__cv` | With selected controls; record `x`. |

Order:

```text
all nocv: y -> x
all cv:   y -> x
```

Count:

```text
n_y * n_x * 2
```

## 2. Robustness

Supported robustness checks:

- `alt_x`
- `alt_y`
- `ln_x`
- `ln_y`
- `lag`
- `year`

Global order:

```text
alt_x -> alt_y -> ln_x -> ln_y -> lag -> year
```

### Alternative X

Enabled when `rob_vars` contains `alt_x`.

Model:

```text
y ~ x_alt + cv_selected
```

Column:

```text
robustness_altx__{y}__{x_alt}
```

Order:

```text
x_alt -> y
```

### Alternative Y

Enabled when `rob_vars` contains `alt_y`.

Model:

```text
y_alt ~ x + cv_selected
```

Column:

```text
robustness_alty__{y_alt}__{x}
```

Order:

```text
y_alt -> x
```

### Log X

Enabled when `x_ln` is enabled for original `x`, or `rob_vars` contains extra `ln_x` targets.

Model:

```text
y ~ ln(x_target) + cv_selected
```

Column:

```text
robustness_lnx__{y}__{x_target}
```

Order:

```text
x_target -> y
```

### Log Y

Enabled when `y_ln` is enabled for original `y`, or `rob_vars` contains extra `ln_y` targets.

Model:

```text
ln(y_target) ~ x + cv_selected
```

Column:

```text
robustness_lny__{y_target}__{x}
```

Order:

```text
y_target -> x
```

### Lagged X

Enabled when `rob_vars` contains `lag`.

Model:

```text
y ~ L{p}.x + cv_selected
```

Column:

```text
robustness_lag__{y}__{x}__l{p}
```

Order:

```text
p -> y -> x
```

### Time Window

Enabled when `rob_year_range` is non-empty.

Model:

```text
y ~ x + cv_selected, if timevar >= left & timevar <= right
```

Column:

```text
robustness_year__{y}__{x}
```

Order:

```text
y -> x
```

Do not generate separate `lc1/lc0` subsample robustness sections in the current workflow.

## 3. IV

For each `(y, x, iv)`, run:

- First stage: `x ~ iv + cv_selected`
- Second stage: 2SLS/IV estimator for `y ~ x + cv_selected`

The second stage records the endogenous `x` coefficient from the IV estimator, not an ordinary OLS coefficient.

Columns:

| Column | Meaning |
| --- | --- |
| `iv__{y}__{x}__{iv}__stage1` | First stage; record `iv`. |
| `iv__{y}__{x}__{iv}__stage2` | Second stage; record `x`. |

Order:

```text
y -> x -> iv -> stage1/stage2
```

Count:

```text
n_y * n_x * n_iv * 2
```

## 4. Mediation

Current mediation means a mechanism-check section, not full mediation-effect identification.

For each mediator `med`, run:

- Total effect: `y ~ x + cv_selected`
- Path a: `med ~ x + cv_selected`

Columns:

| Column | Meaning |
| --- | --- |
| `mediation__{med}__{y}__{x}` | Total effect; record `x`. |
| `mediation__{med}__M__{x}` | Path a; record `x`. |

Order:

```text
med -> total_effect(y -> x) -> path_a(x)
```

Count:

```text
n_meds * (n_y * n_x + n_x)
```

## 5. Moderation

Moderation tests interactions with continuous moderators.

Model:

```text
y ~ std(x) * std(mod) + cv_selected
```

Record the interaction coefficient.

Column:

```text
moderation__{mod}__{y}__{x}
```

Order:

```text
mod -> y -> x
```

Count:

```text
n_mods * n_y * n_x
```

## 6. Discrete Heterogeneity

Discrete heterogeneity runs group-specific regressions for selected group values.

Model:

```text
y ~ x + cv_selected, if group_var == group_value
```

Column:

```text
heterogeneity_group__{group_var}__{group_value}__{y}__{x}
```

Order:

```text
group_var -> group_value -> y -> x
```

Count:

```text
sum(n_group_values(group_var)) * n_y * n_x
```
