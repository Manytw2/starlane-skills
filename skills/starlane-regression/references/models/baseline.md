# Module: Baseline

## Purpose

基准回归用来回答：核心解释变量和被解释变量之间是否存在稳定的统计关系。

Baseline regression is required for the workflow.

## Candidate Signals

The agent may suggest:

- likely outcomes from research terms, log-prefixed variables, or user-provided topic
- likely core explanatory variables from the user's research question
- panel entity and time variables from names such as `id`, `firm_id`, `year`
- controls from common firm or region variables such as size, leverage, age, ROA, ownership, governance, macro controls

These are only candidate mappings. The user must confirm.

## Control Recommendation

In guided setup mode, do not recommend only a flat control-variable pool.

When candidate controls exist, recommend a complete control setting:

- the shared control-variable pool for candidate settings
- locked baseline controls that every candidate control combination should include
- the minimum number of controls in each candidate control combination
- the implied search workload

The control-variable pool maps to `baseline.controls.search_pool`. It includes
both locked controls and optional controls. Locked controls map to
`baseline.controls.always_include` and must be a subset of the control-variable
pool.

Do not silently use `always_include: []` and `min_count: 0` in guided setup
unless that is the agent's explicit research recommendation. Those values are
valid engineering inputs, but they are not automatically reasonable research
defaults.

For the internal default recommendation, if the control-variable pool has `N`
variables, set:

```text
min_count = max(round(0.4 * N), len(always_include))
```

Use this as an internal heuristic for generating a concrete recommendation.
Do not explain the heuristic to the user unless they ask why that number was
recommended. User-facing guidance should state the recommended locked controls,
optional controls, minimum count, and workload directly.

## Confirmation Wording

Use:

```text
基准回归里，被解释变量先选择 ...，核心解释变量选择 ...，可以吗？
```

Use:

```text
个体维度看起来是 id，时间维度看起来是 year。这个面板结构是否符合你的数据？
```

Use:

```text
控制变量设定建议：锁变量 / 基础控制变量包括 ...；其他可选控制变量包括 ...；每套候选控制变量组合至少包含 ... 个控制变量。
```

Use:

```text
同一套候选控制变量组合会用于基准回归、稳健性检验、机制检验和调节检验，方便横向比较。
```

## Analysis Plan

Write confirmed values into:

- `baseline.enabled`
- `baseline.outcomes`
- `baseline.explanatory_vars`
- `baseline.controls.search_pool`
- `baseline.controls.always_include`
- `baseline.controls.min_count`
- `baseline.fixed_effects.entity`
- `baseline.fixed_effects.time`
- `baseline.vce_policy`

## Section Schema

For each `(y, x)`, run:

| Block | Formula | Column | Records | Order |
| --- | --- | --- | --- | --- |
| No controls | `y ~ x` | `baseline__{y}__{x}__nocv` | `x` | `y -> x` |
| With controls | `y ~ x + cv_selected` | `baseline__{y}__{x}__cv` | `x` | `y -> x` |

Global order:

```text
all nocv: y -> x
all cv:   y -> x
```

Count:

```text
n_y * n_x * 2
```

## Regression Args

| Analysis plan field | Regression arg |
| --- | --- |
| `data.input_path` | `data_path` |
| `baseline.outcomes` | `y` |
| `baseline.explanatory_vars` | `x` |
| `baseline.controls.search_pool` | `cv` |
| `baseline.controls.always_include` | `cv_fixed` |
| `baseline.controls.min_count` | `cv_min_count` |
| `baseline.fixed_effects.entity` | `panelvar` |
| `baseline.fixed_effects.time` | `timevar` |
| `research.expected_direction` | `coef_direction` |

## Boundaries

Do not imply causal identification from baseline regression alone.

Do not choose controls only because they maximize significance.
