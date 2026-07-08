# Module: Robustness

## Purpose

稳健性检验用来检查主结论是否依赖某一种变量定义、时间设定或模型设定。

## When To Recommend

Recommend robustness checks when the data contain:

- alternative outcome variables
- alternative explanatory variables
- meaningful lag structures
- a useful sample-year window
- variables that can be defensibly log-transformed

## Confirmation Wording

Use:

```text
稳健性检验里，可以用 ... 作为替代被解释变量，检验结论是否依赖原来的结果变量定义。
```

Use:

```text
还可以加入核心解释变量的一期滞后，降低同步性解释的压力。
```

Use:

```text
当前变量名里已经有 ln 开头的变量，所以我不建议默认再做取对数稳健性，除非你确认原始变量适合这样处理。
```

## Analysis Plan

Write confirmed values into:

- `robustness.enabled`
- `robustness.alternative_outcomes`
- `robustness.alternative_explanatory_vars`
- `robustness.lag_periods`
- `robustness.log_y`
- `robustness.log_x`
- `robustness.sample_window`

## Section Schema

Global order:

```text
alt_x -> alt_y -> ln_x -> ln_y -> lag -> year
```

| Check | Enabled by | Formula | Column | Order |
| --- | --- | --- | --- | --- |
| Alternative X | `robustness.alternative_explanatory_vars` | `y ~ x_alt + cv_selected` | `robustness_altx__{y}__{x_alt}` | `x_alt -> y` |
| Alternative Y | `robustness.alternative_outcomes` | `y_alt ~ x + cv_selected` | `robustness_alty__{y_alt}__{x}` | `y_alt -> x` |
| Log X | `robustness.log_x` | `y ~ ln(x_var) + cv_selected` | `robustness_lnx__{y}__{x_var}` | `x_var -> y` |
| Log Y | `robustness.log_y` | `ln(y_var) ~ x + cv_selected` | `robustness_lny__{y_var}__{x}` | `y_var -> x` |
| Lagged X | `robustness.lag_periods` | `y ~ L{p}.x + cv_selected` | `robustness_lag__{y}__{x}__l{p}` | `p -> y -> x` |
| Time Window | `robustness.sample_window` | `y ~ x + cv_selected` within the selected time window | `robustness_year__{y}__{x}` | `y -> x` |

Do not generate separate `lc1/lc0` subsample robustness sections.

## Compiled Contract

The compiler preserves the public contract as structured `regression_args.json`.
Env scripts may translate these fields into internal execution variables, but users and agents should not write those internal variables directly.

| Analysis plan field | Structured `regression_args.json` field |
| --- | --- |
| `robustness.alternative_outcomes` | `robustness.alternative_outcomes` |
| `robustness.alternative_explanatory_vars` | `robustness.alternative_explanatory_vars` |
| `robustness.lag_periods` | `robustness.lag_periods` |
| `robustness.log_y` | `robustness.log_y` |
| `robustness.log_x` | `robustness.log_x` |
| `robustness.sample_window` | `robustness.sample_window` |

`robustness.lag_periods` contains positive integer periods, not variable names.
For example, `[1]` means one-period lags of all core explanatory variables.

## Boundaries

Do not frame robustness as proof of causality.

If many robustness checks are enabled only after seeing significance, flag selection risk.
