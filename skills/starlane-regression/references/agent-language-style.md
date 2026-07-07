# Agent Language Style

This reference controls how agents discuss regression setup with users.

The user-facing language must sound like empirical research guidance, not regression parameter collection.

## Core Rule

Regression args are implementation details. Use research-language labels when speaking with users.

| Regression arg | User-facing wording |
| --- | --- |
| `input_dta` | 数据文件 |
| `y` | 被解释变量, 结果变量 |
| `x` | 核心解释变量, 解释变量 |
| `cv` | 控制变量池 |
| `cv_fixed` | 每个模型都保留的基础控制变量 |
| `cv_min_count` | 每个候选模型至少包含的控制变量数量 |
| `panelvar` | 个体维度, 企业 ID, 样本主体 |
| `timevar` | 时间维度, 年份 |
| `meds` | 机制变量, 中介变量 |
| `mods` | 调节变量 |
| `heterogeneity_discrete` | 分组异质性变量 |
| `heterogeneity_discrete_values` | 分组异质性的取值 |
| `rob_vars` | 稳健性检验设置 |
| `y_ln` | 是否对被解释变量取对数做稳健性 |
| `x_ln` | 是否对核心解释变量取对数做稳健性 |
| `rob_year_range` | 稳健性检验的样本年份窗口 |
| `iv` | 工具变量候选 |
| `coef_direction` | 预期影响方向 |
| `vce_idx` | 标准误处理方式 |

## Required Inference Boundary

Before suggesting variable roles, say:

```text
我先根据数据里的列名和基本结构做一个初步判断。因为变量名是你在数据中命名的，我只能从名称、类型、缺失情况和常见经管研究习惯推断变量角色，不能保证理解完全正确；如果某个变量的实际含义和我的推断不一致，以你的解释为准。
```

## Preferred Wording

Use:

```text
基准回归里，被解释变量先选择 lnApplyG 和 lnGrantG，可以吗？
```

Do not use:

```text
y: lnApplyG lnGrantG 对吗？
```

Use:

```text
核心解释变量选择 Attention，可以吗？
```

Do not use:

```text
x: Attention 对吗？
```

Use:

```text
机制检验里，机制变量选择 Charge、Subsidy、lnCSR，可以吗？
```

Do not use:

```text
meds: Charge|Subsidy|lnCSR 对吗？
```

Use:

```text
调节效应里，调节变量选择 OverSea、lnMediaPos、lnMediaNeg，可以吗？
```

Do not use:

```text
mods: OverSea|lnMediaPos|lnMediaNeg 对吗？
```

## Agent Posture

The agent is a research assistant, not a gatekeeper.

Do not say:

```text
你必须解释清楚工具变量外生性，否则不能做 IV。
```

Say:

```text
Thermalinv 可以先作为工具变量候选。我们需要一起判断它是否适合支撑主识别；如果还说不清，结果里应把 IV 写成探索性检验，而不是强因果证明。
```

## Regression Args

Regression arg names may appear in:

- reproducibility notes
- generated source explanations
- regression args JSON
- developer-facing debugging

They should not be the primary language for user confirmation.
