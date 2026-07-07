# Module: IV

## Purpose

工具变量检验用来探索核心解释变量可能存在的内生性问题。

The agent should discuss IV as a research-design choice with the user. It should not act as a gatekeeper, but it also should not present IV as automatic causal proof.

## When To Discuss

Discuss IV when the user provides candidate instruments or the data contain plausible instrument-like variables.

## Confirmation Wording

Use:

```text
Thermalinv 可以先作为工具变量候选。我们需要一起判断它是否适合支撑主识别；如果还说不清，结果里应把 IV 写成探索性检验，而不是强因果证明。
```

Do not say:

```text
你必须解释清楚外生性，否则不能做 IV。
```

## Analysis Plan

Write confirmed values into:

- `iv.enabled`
- `iv.instruments`
- `iv.interpretation_policy`

`interpretation_policy` should be:

- `exploratory` when the instrument is only a candidate
- `main_identification` only when the research design has been explicitly confirmed

## Section Schema

For each `(y, x, iv)`, run:

| Block | Formula | Column | Records | Order |
| --- | --- | --- | --- | --- |
| First stage | `x ~ iv + cv_selected` | `iv__{y}__{x}__{iv}__stage1` | `iv` | `y -> x -> iv -> stage1` |
| Second stage | IV estimator for `y ~ x + cv_selected` | `iv__{y}__{x}__{iv}__stage2` | endogenous `x` coefficient | `y -> x -> iv -> stage2` |

The second stage records the endogenous `x` coefficient from the IV estimator, not an ordinary OLS coefficient.

Count:

```text
n_y * n_x * n_iv * 2
```

## Regression Args

| Analysis plan field | Regression arg |
| --- | --- |
| `iv.instruments` | `iv` |

## Boundaries

Do not state that IV proves causality unless identification assumptions are explicitly discussed.

For undergraduate thesis support, prefer cautious language unless the user has a clear design.
