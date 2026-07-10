# Module: Heterogeneity

## Purpose

异质性检验用来比较不同分组中核心关系是否不同。

## When To Ask

Ask about heterogeneity when the data contain discrete grouping variables, such as:

- ownership type
- region
- industry category
- pollution status
- low-carbon classification

Do not silently enable it. The user should confirm which grouping has research meaning.

## Confirmation Wording

Use:

```text
异质性检验里，SOE、East、poll、lowcarbon 看起来像分组变量。你是否希望比较这些分组下 Attention 的影响差异？
```

## Analysis Plan

Write confirmed values into:

- `heterogeneity.enabled`
- `heterogeneity.discrete_groups`
- `heterogeneity.selected_values`

## Section Schema

Discrete heterogeneity runs group-specific regressions for selected group values.

| Block | Formula | Column | Records | Order |
| --- | --- | --- | --- | --- |
| Group-specific regression | `y ~ x + cv_selected` within `group_var == group_value` | `het_disc__{group_var}__{group_value}__{y}__{x}` | `x` | `group_var -> group_value -> y -> x` |

Count:

```text
sum(n_group_values(group_var)) * n_y * n_x
```

## Regression Args

| Analysis plan field | Regression arg |
| --- | --- |
| `heterogeneity.discrete_groups` | `het_disc` |
| `heterogeneity.selected_values` | `het_disc_vals` |

Encoded selected values use:

```text
het_disc = SOE|Region
het_disc_vals = SOE:1;0|Region:East;West
```

## Group N vs Full-Sample N

Group Ns are not required to sum to the full-sample N. Both `reghdfe` and
`pyfixest` drop singleton fixed effects, and splitting the base sample by a
group variable can create new singletons: an entity whose group membership
changes over time may have only one observation left inside a group, and that
observation is dropped from the group regression.

- Time-invariant group variables (each entity stays in one group) do not
  create new singletons, so their group Ns sum exactly to the full-sample N.
- Time-varying group variables (e.g. ownership changes, entering/leaving a
  classification) typically leave the group-N sum slightly below the
  full-sample N. This is standard two-way fixed-effects behavior, not a
  sampling bug; note it in the table footnote instead of "fixing" it.

Both envs report the post-drop effective N (Stata `e(N)`; Python uses the
pyfixest effective N).

## Boundaries

Do not create arbitrary groups only to search for significant results.

If a group has very small sample size, flag it before final interpretation.
