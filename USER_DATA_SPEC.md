# 用户数据与实证分析指导书

本文件定义回归类 skill 必须理解和保留的参数维度、变量映射、实证分析方法思路和展开规则。它是后续补齐 skill 文档与实现的依据。

本指导书不包含加密、提取码、兑换流程、产品私有路径、隐藏目录等旧链路细节。

---

## 目标范围

当前 skill 面向用户已经提供数据和变量角色的回归交付 workflow。

必须覆盖以下 6 类实证分析方法：

- baseline
- robustness
- IV
- mediation
- moderation
- discrete heterogeneity

skill 可以使用 Stata 或 Python 作为执行后端，但二者必须服务同一套参数和 section schema。后端只是执行方式，不是两套业务逻辑。

---

## 输入契约

输入由两部分组成：

- 数据文件：用户提供的面板或截面数据。
- 变量角色映射：用户说明每个变量在实证分析中的角色。

skill 必须先校验输入，再进入 summary 阶段。不能凭变量名猜测角色，不能自动发明变量，不能在用户未声明时扩展到本指导书外的方法。

### 必填输入

| 字段 | 格式 | 说明 |
| --- | --- | --- |
| `input_dta` | 文件路径 | 输入数据文件。支持 `.dta`、`.xlsx`、`.xls`、`.csv`。 |
| `y` | 空格分隔 | 因变量，可多个。 |
| `x` | 空格分隔 | 核心自变量，可多个。 |
| `cv` | 空格分隔 | 控制变量全集。 |
| `panelvar` | 单个变量名 | 个体变量，例如 `id`、`firm_id`。 |
| `timevar` | 单个变量名 | 时间变量，例如 `year`。 |

必填字段缺失时必须停止，并明确指出缺失项。

### 可选输入

| 字段 | 格式 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `cv_fixed` | 空格分隔 | 空 | 固定必选控制变量，必须是 `cv` 的子集。 |
| `cv_min_count` | 整数 | `0` | 每个控制变量组合至少包含多少个控制变量。 |
| `rob_vars` | `type:value|type:value` | 空 | 稳健性变量配置。 |
| `y_ln` | 布尔式字符串 | 启用 | 是否对原始 `y` 做取对数稳健性。 |
| `x_ln` | 布尔式字符串 | 启用 | 是否对原始 `x` 做取对数稳健性。 |
| `rob_year_range` | `left:right` | 空 | 稳健性样本期，例如 `2015:2020`。 |
| `iv` | 空格分隔 | 空 | 工具变量。 |
| `meds` | `|` 分隔 | 空 | 中介或机制变量。 |
| `mods` | `|` 分隔 | 空 | 调节变量。 |
| `heterogeneity_discrete` | `|` 分隔 | 空 | 离散分组异质性变量。 |
| `heterogeneity_discrete_values` | `var:v1;v2|var2:v3;v4` | 空 | 每个离散分组变量选中的取值。 |
| `coef_direction` | `positive` 或 `negative` | `positive` | 预期方向，只用于 summary 阶段评分和剪枝。 |

### 输入校验

进入回归前必须校验：

- 数据文件存在，格式受支持。
- 所有必填字段非空。
- `y`、`x`、`cv`、`panelvar`、`timevar` 对应变量存在于数据中。
- `cv_fixed` 是 `cv` 的子集。
- `cv_min_count` 是非负整数，且不超过 `cv` 数量。
- `coef_direction` 只能是 `positive` 或 `negative`。
- `rob_vars` 的 type 只能是 `alt_x`、`alt_y`、`ln_x`、`ln_y`、`lag`。
- `lag` 只能包含正整数滞后阶数。
- `rob_year_range` 必须能解析为左边界小于等于右边界的时间区间。
- `heterogeneity_discrete_values` 中声明的 key 必须能对应 `heterogeneity_discrete` 中的变量。

### 标准参数顺序

当执行后端需要位置参数时，使用以下标准顺序：

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

final 阶段在上述参数后追加：

```text
cv_idx
vce_idx
```

---

## 面板与聚类映射

只传递 `panelvar` 和 `timevar`。执行层由它们推导聚类变量：

```text
cluster_var  = panelvar
cluster_var2 = timevar
```

不存在缺失时的回退逻辑。`panelvar` 和 `timevar` 必须存在于数据中。

VCE 类型固定为 4 类：

| `vce_idx` | `vce_suffix` | 说明 |
| --- | --- | --- |
| `0` | `ols` | 常规标准误。 |
| `1` | `robust` | 稳健标准误。 |
| `2` | `cluster_{panelvar}` | 按个体聚类。 |
| `3` | `cluster_{panelvar}_{timevar}` | 按个体和时间双向聚类。 |

---

## 控制变量组合

summary 阶段需要枚举控制变量组合。

规则：

- `cv` 是控制变量全集。
- `cv_fixed` 中的变量必须出现在每个组合中。
- `cv_fixed` 必须是 `cv` 的子集。
- `cv_min_count` 约束每个组合的总控制变量数量。
- 每个有效控制变量组合分配一个 `cv_idx`。
- 最终选择用 `cv_idx + vce_idx` 还原选中的控制变量组合和 VCE 类型。

skill 不应使用加密字符串、提取码或 password 来表达选择结果。

---

## 稳健性变量格式

`rob_vars` 使用如下格式：

```text
type:value|type:value
```

`value` 内部使用空格分隔多个变量或滞后阶数。

| type | 示例 | 说明 |
| --- | --- | --- |
| `alt_x` | `alt_x:x2 x3` | 使用替代 X 变量做稳健性。 |
| `alt_y` | `alt_y:y2 y3` | 使用替代 Y 变量做稳健性。 |
| `ln_x` | `ln_x:x2` | 额外对指定 X 变量取对数。 |
| `ln_y` | `ln_y:y2` | 额外对指定 Y 变量取对数。 |
| `lag` | `lag:1 2 3` | 使用 `L1.x`、`L2.x`、`L3.x` 等滞后 X。 |

`y_ln` 和 `x_ln` 控制是否对原始 `y`、`x` 自动取对数：

- 空值、`1`、`yes`、`true`、`是` 表示启用。
- `0`、`no`、`false`、`否` 表示跳过。

`rob_vars.ln_x` 和 `rob_vars.ln_y` 是额外取对数目标，可以和 `x_ln`、`y_ln` 叠加。实现应去重，避免同一个变量重复生成同一类稳健性。

---

## 离散异质性取值格式

`heterogeneity_discrete` 声明分组变量：

```text
SOE|Region
```

`heterogeneity_discrete_values` 声明每个变量选中的分组值：

```text
SOE:1;0|Region:East;West
```

规则：

- `:` 左侧是分组变量名。
- `;` 分隔同一分组变量的多个取值。
- `|` 分隔多个分组变量。
- 当变量名或取值包含特殊字符时，调用方可以 URL 编码后传递；解析层必须能还原。
- 输出列名和 section schema 应使用稳定、可解析的取值表示，避免中文、空格或特殊字符破坏 CSV header。

---

## 输出契约

输出分为两个阶段：

- summary 阶段：生成候选模型组合表，供用户选择。
- final 阶段：按用户选择生成可复现源码和最终结果。

### Summary 输出

summary 阶段必须输出 `combination_summary.csv`。

每一行代表一个 `cv_idx + vce_idx` 候选组合。固定列必须包含：

| 列名 | 说明 |
| --- | --- |
| `selection_id` | 明文选择标识，格式为 `{cv_idx}_{vce_idx}`。 |
| `cv_idx` | 控制变量组合索引。 |
| `vce_idx` | VCE 类型索引。 |
| `vce_suffix` | VCE 类型名称。 |
| `cv_selected` | 当前组合选中的控制变量，用 `|` 拼接；空组合为空字符串。 |
| `score` | 综合得分，通常为各 section 方向一致显著性星号分数之和。 |

固定列之后是动态系数列。动态列由后文 6 类方法的 section schema 展开得到。

系数单元格格式：

```text
{coef}{stars}
```

规则：

- `coef` 是对应模型中目标变量的系数。
- `stars` 根据 `coef_direction` 做方向一致性判断后附加。
- `***` 表示 `p < 0.01`。
- `**` 表示 `p < 0.05`。
- `*` 表示 `p < 0.1`。
- 空星号表示不显著或方向不一致。
- 回归失败、样本不足或目标系数缺失时，该单元格留空。

summary 输出不得包含加密选择字段、提取码或 password。

### Final 输出

final 阶段输入为：

```text
原始输入参数 + cv_idx + vce_idx
```

final 阶段必须输出：

| 产物 | 说明 |
| --- | --- |
| 最终源码 | 可读、可复现的 `.do` 或 `.py` 文件。 |
| 结果表 | 运行最终源码后生成的回归结果表；优先输出 Word 文档。 |
| 运行记录 | 说明后端、参数、选中组合、执行是否成功。 |
| 复现说明 | 说明如何用同一输入和选择重新生成结果。 |

最终源码必须显式体现：

- `cv_idx` 对应的 `cv_selected`。
- `vce_idx` 对应的 VCE 设定。
- `panelvar/timevar` 到聚类变量的映射。
- 启用的 6 类实证分析板块。
- 每个板块展开出的模型顺序。

如果本地环境缺少 Stata、Python 依赖或 Word 导出依赖，skill 仍应尽量生成最终源码，并清楚说明未能执行的原因。

---

## Section Schema 总原则

summary 阶段和 final 阶段必须共享同一套 section schema。

要求：

- summary 表的动态列展开规则必须和 final 代码生成的模型块展开规则一致。
- Stata backend 和 Python backend 必须使用同一套 section schema。
- 列名使用 `__` 作为段分隔符，避免变量名含单个下划线时产生歧义。
- 各 section 的启用条件、展开维度、循环顺序必须稳定。
- final 阶段用用户选择的 `cv_idx + vce_idx` 还原 `cv_selected + vce`，再生成可读、可复现的源码。

---

## 方法 1：Baseline

baseline 对每个 `(y, x)` 组合固定展开两类回归：

- 无控制变量：`y ~ x`
- 有控制变量：`y ~ x + cv_selected`

列名：

| 列名模式 | 说明 |
| --- | --- |
| `baseline__{y}__{x}__nocv` | 无控制变量，记录 `x` 系数。 |
| `baseline__{y}__{x}__cv` | 有控制变量，记录 `x` 系数。 |

展开顺序：

1. 先展开全部 `nocv`，循环顺序为 `y -> x`。
2. 再展开全部 `cv`，循环顺序为 `y -> x`。

列数：

```text
n_y * n_x * 2
```

---

## 方法 2：Robustness

robustness 包含 6 类子检查：

- 替换 X：`alt_x`
- 替换 Y：`alt_y`
- X 取对数：`ln_x`
- Y 取对数：`ln_y`
- 滞后 X：`lag`
- 时间窗口：`year`

总顺序固定为：

```text
alt_x -> alt_y -> ln_x -> ln_y -> lag -> year
```

### 替换 X

启用条件：`rob_vars` 包含 `alt_x`。

模型思路：

```text
y ~ x_alt + cv_selected
```

列名：

```text
robustness_altx__{y}__{x_alt}
```

展开顺序：

```text
x_alt -> y
```

### 替换 Y

启用条件：`rob_vars` 包含 `alt_y`。

模型思路：

```text
y_alt ~ x + cv_selected
```

列名：

```text
robustness_alty__{y_alt}__{x}
```

展开顺序：

```text
y_alt -> x
```

### X 取对数

启用条件：

- `x_ln` 为启用时，对原始 `x` 做取对数稳健性。
- `rob_vars` 包含 `ln_x` 时，对指定额外变量做取对数稳健性。

模型思路：

```text
y ~ ln(x_target) + cv_selected
```

列名：

```text
robustness_lnx__{y}__{x_target}
```

展开顺序：

```text
x_target -> y
```

### Y 取对数

启用条件：

- `y_ln` 为启用时，对原始 `y` 做取对数稳健性。
- `rob_vars` 包含 `ln_y` 时，对指定额外变量做取对数稳健性。

模型思路：

```text
ln(y_target) ~ x + cv_selected
```

列名：

```text
robustness_lny__{y_target}__{x}
```

展开顺序：

```text
y_target -> x
```

### 滞后 X

启用条件：`rob_vars` 包含 `lag`。

模型思路：

```text
y ~ L{p}.x + cv_selected
```

列名：

```text
robustness_lag__{y}__{x}__l{p}
```

展开顺序：

```text
p -> y -> x
```

### 时间窗口

启用条件：`rob_year_range` 非空，格式为 `year_left:year_right`。

模型思路：

```text
y ~ x + cv_selected, if timevar >= year_left & timevar <= year_right
```

列名：

```text
robustness_year__{y}__{x}
```

展开顺序：

```text
y -> x
```

当前标准链路不单独生成 `lc1/lc0` 子样本稳健性板块；时间窗口是保留的子样本稳健性形式。

---

## 方法 3：IV

IV 对每个 `(y, x, iv)` 组合展开两类结果：

- 一阶段
- 二阶段

一阶段模型思路：

```text
x ~ iv + cv_selected
```

二阶段模型思路：

```text
y ~ x + cv_selected
```

二阶段应使用 2SLS/IV estimator，例如 Stata 中的 `ivreghdfe`。记录内生解释变量 `x` 的二阶段系数，而不是普通 OLS 系数。

列名：

| 列名模式 | 说明 |
| --- | --- |
| `iv__{y}__{x}__{iv}__stage1` | 一阶段，记录 `iv` 系数。 |
| `iv__{y}__{x}__{iv}__stage2` | 二阶段，记录 `x` 系数。 |

展开顺序：

```text
y -> x -> iv -> stage1/stage2
```

列数：

```text
n_y * n_x * n_iv * 2
```

---

## 方法 4：Mediation

当前 mediation 指“机制检验板块”，不是完整中介效应识别流程。

对每个中介变量 `med` 展开两类结果：

- 总效应：`y ~ x + cv_selected`
- 路径 a：`med ~ x + cv_selected`

列名：

| 列名模式 | 说明 |
| --- | --- |
| `mediation__{med}__{y}__{x}` | 总效应，记录 `x` 系数。 |
| `mediation__{med}__M__{x}` | 路径 a，记录 `x` 系数。 |

展开顺序：

```text
med -> total_effect(y -> x) -> path_a(x)
```

列数：

```text
n_meds * (n_y * n_x + n_x)
```

---

## 方法 5：Moderation

moderation 用连续调节变量检验交互项。

模型思路：

```text
y ~ std(x) * std(mod) + cv_selected
```

记录交互项系数。

列名：

```text
moderation__{mod}__{y}__{x}
```

展开顺序：

```text
mod -> y -> x
```

列数：

```text
n_mods * n_y * n_x
```

---

## 方法 6：Discrete Heterogeneity

discrete heterogeneity 对离散分组变量的指定取值分别做分组回归。

模型思路：

```text
y ~ x + cv_selected, if group_var == group_value
```

列名：

```text
heterogeneity_group__{group_var}__{group_value}__{y}__{x}
```

展开顺序：

```text
group_var -> group_value -> y -> x
```

列数：

```text
sum(n_group_values(group_var)) * n_y * n_x
```

典型分组包括地区、行业、产权、是否国企等离散变量。

---

## 剪枝规则

summary 阶段可以进行剪枝以减少运行时间。

推荐规则：

如果某个 `cv_idx + vce_idx` 下所有 baseline-with-cv 的核心解释变量 `x` 均不显著，或方向与 `coef_direction` 不一致，则可以跳过该组合下的 robustness、IV、mediation、moderation、discrete heterogeneity。

剪枝只影响 summary 阶段搜索效率，不改变 final 阶段用户选中模型的回归公式。

---

## 执行链路

标准链路：

1. summary 阶段枚举 `cv_idx` 与 `vce_idx`。
2. 输出 `combination_summary.csv`。
3. 用户选择一行候选结果，或明确授权系统按规则选择。
4. final 阶段使用同一组原始参数，加上 `cv_idx + vce_idx`。
5. final 阶段还原 `cv_selected + vce`。
6. 生成可读、可复现的最终源码。
7. 在可执行环境存在时运行最终源码并产出结果文档。

最终源码必须能说明：

- 使用了哪些 `y`、`x`、`cv_selected`。
- 使用了哪种 VCE。
- 启用了哪些实证分析板块。
- 每个板块对应哪些变量维度。

---

## Skill 文档最低要求

skill 的 Markdown 文档至少要说明：

- 支持哪些输入字段。
- 必填字段有哪些。
- `panelvar/timevar` 如何映射到聚类变量。
- `cv_fixed/cv_min_count` 如何影响控制变量组合。
- `rob_vars` 支持哪些 type。
- 6 类方法各自的模型思路和展开维度。
- summary 表如何让用户选择 `cv_idx + vce_idx`。
- final 阶段如何复现用户选中的组合。
- 当前 mediation 只是机制检验板块，不等同完整中介效应识别。
- 当前不支持 DID、RDD、PSM、SCM、DML、event study 等本指导书外的方法，除非另行扩展。
