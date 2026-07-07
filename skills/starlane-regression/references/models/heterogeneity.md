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
| Group-specific regression | `y ~ x + cv_selected` within `group_var == group_value` | `heterogeneity_group__{group_var}__{group_value}__{y}__{x}` | `x` | `group_var -> group_value -> y -> x` |

Count:

```text
sum(n_group_values(group_var)) * n_y * n_x
```

## Regression Args

| Analysis plan field | Regression arg |
| --- | --- |
| `heterogeneity.discrete_groups` | `heterogeneity_discrete` |
| `heterogeneity.selected_values` | `heterogeneity_discrete_values` |

Encoded selected values use:

```text
heterogeneity_discrete = SOE|Region
heterogeneity_discrete_values = SOE:1;0|Region:East;West
```

## Boundaries

Do not create arbitrary groups only to search for significant results.

If a group has very small sample size, flag it before final interpretation.
