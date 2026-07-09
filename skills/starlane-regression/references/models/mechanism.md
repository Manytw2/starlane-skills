# Module: Mechanism

## Purpose

机制检验用来讨论核心解释变量可能通过哪些路径影响被解释变量。

Current mechanism output is a mechanism-check section, not a full causal mediation-effect decomposition.

## When To Recommend

Recommend this module when the data contain plausible pathway variables, such as:

- policy or regulatory pressure
- subsidy or financing channels
- CSR or governance channels
- media or information channels

## Confirmation Wording

Use:

```text
机制检验里，... 可能代表作用路径。我们可以把它作为机制变量，看看 Attention 是否与这些路径变量相关。
```

Do not say:

```text
meds 是 ...
```

## Analysis Plan

Write confirmed values into:

- `mechanism.enabled`
- `mechanism.variables`

## Section Schema

For each mechanism variable `med`, run:

| Block | Formula | Column | Records | Order |
| --- | --- | --- | --- | --- |
| Total effect | `y ~ x + cv_selected` | `med__{med}__{y}__{x}` | `x` | `med -> y -> x` |
| Path a | `med ~ x + cv_selected` | `med__{med}__M__{x}` | `x` | `med -> x` |

Count:

```text
n_meds * (n_y * n_x + n_x)
```

## Regression Args

| Analysis plan field | Regression arg |
| --- | --- |
| `mechanism.variables` | `meds` |

## Boundaries

Do not claim a full mediation effect unless the design supports it.

Use wording such as:

```text
机制证据
可能路径
机制相关性
```

Avoid wording such as:

```text
证明中介效应成立
完全解释了影响机制
```
