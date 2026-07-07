# Starlane Regression Workflow 设计草稿

## 当前判断

Starlane 的长期目标可以分成四个阶段：

```text
制定主题
收集清理数据
建模回归分析
落文章
```

当前第一版只落地第三阶段：建模回归分析。

这一阶段的核心不是做一个覆盖所有实证方法的模板库，而是封装一套能稳定交付结果的 regression delivery workflow。它从用户提供的数据和变量映射出发，先产出模型组合汇总表，再由用户选择候选行，最后输出最终结果、可复现源码和结果说明。

Python 和 Stata 是可选执行后端。它们是实现语言，不是两个独立 workflow。

## 术语约定

旧项目中的 `motion` 是历史遗留命名。Starlane 项目中不继续使用这个词。

当前统一使用：

- `regression delivery workflow`
- `summary stage`
- `final stage`
- `backend`
- `source artifact`

除非引用旧文件名或旧系统接口，否则文档中不再把核心链路称为 `motion` 或 `script workflow`。

## 当前能力边界

当前正式能力边界以这些文件为准：

```text
skills/starlane-regression/SKILL.md
skills/starlane-regression/references/user-data-and-io-contract.md
skills/starlane-regression/references/empirical-section-schema.md
skills/starlane-regression/references/supported-methods.md
skills/starlane-regression/references/workflow-contract.md
skills/starlane-regression/references/ethics-and-boundaries.md
```

这些文件定义第一版的输入、输出、支持方法、工作流约定和边界说明。正式规范没有定义的检验，当前 Starlane 不承诺支持，也不应由 Agent 临时编造。

当前支持的主要板块包括：

- 基准回归
- 控制变量组合枚举
- 标准误类型枚举
- 稳健性检验：替换 X
- 稳健性检验：替换 Y
- 稳健性检验：X 取对数
- 稳健性检验：Y 取对数
- 稳健性检验：滞后 X
- 稳健性检验：时间窗口
- 工具变量：一阶段、二阶段
- 中介机制
- 调节效应
- 离散分组异质性
- 描述性统计
- 汇总表与最终源码生成

当前不支持的内容包括但不限于：

- DID
- Event Study
- RDD
- PSM
- SCM
- DML
- Causal Forest
- Bayesian
- Survival
- Oaxaca
- QTE
- 自动寻找数据
- 自动制定完整论文主题
- 自动写完整论文
- 正式契约之外的检验或识别策略

## 第一版 Skill 定位

第一版不做完整实证分析全链路。

第一版只做一个深、窄、边界清楚的 skill：

```text
starlane-regression
```

它对应四阶段中的第三阶段：建模回归分析。

它的目标是把当前 regression delivery workflow 彻底落地，而不是提前扩展到其他阶段。

## starlane-regression 的职责

`starlane-regression` 应负责：

- 读取并遵守正式共享契约
- 判断用户请求是否在当前支持范围内
- 收集和校验必填变量映射
- 规范化可选参数
- 确认执行后端：Python 或 Stata
- 调用所选后端的 summary stage
- 读取并交付 `combination_summary.csv`
- 辅助用户理解候选模型
- 等待用户选择候选行，除非用户明确委托 agent 选择
- 调用所选后端的 final stage
- 交付最终结果表、源码、选择说明、局限性和复现说明

它不负责：

- 从零制定论文选题
- 寻找或购买数据
- 大规模数据清洗
- 承诺结果显著
- 承诺因果识别
- 代写完整论文
- 支持当前 contract 之外的方法

## 当前 Workflow

当前链路应理解为两阶段交付：

```text
用户数据 + 变量映射
        ↓
确认后端：Python 或 Stata
        ↓
summary stage
        ↓
.starlane/combination_summary.csv
        ↓
用户选择一行候选结果
        ↓
cv_idx + vce_idx
        ↓
final stage
        ↓
最终结果表 + 可复现源码 + 运行说明
```

Stata 后端当前对应：

```text
regression_summary.do
        ↓
combination_summary.csv
        ↓
generate_regression_do.py
        ↓
regression_generated.do
        ↓
运行最终 .do
```

其中：

- `regression_summary.do` 是 summary stage 的 Stata 实现。
- `generate_regression_do.py` 是 Stata final stage 的源码生成器，本质是根据参数和选择行生成可读 `.do`。
- 根目录 `scripts/stata-code-examples/` 只放给人看的 Stata 展示示例，不属于 workflow 输入。

Python 后端应保持同一套 workflow 语义：

```text
summary stage -> combination_summary.csv
final stage -> final result + .py source artifact
```

## 选择标识

开源版使用透明选择标识。

`combination_summary.csv` 固定暴露：

```text
selection_id
cv_idx
vce_idx
vce_suffix
cv_selected
score
```

约定：

- `selection_id = {cv_idx}_{vce_idx}`
- `cv_idx` 是控制变量子集枚举索引
- `vce_idx` 是标准误类型索引
- `cv_selected` 是被选中的控制变量
- `score` 是排序辅助，不是研究设计证明

不再使用：

- `password`
- XOR
- hex encoding
- hidden selection key

## Skill 不应过度承诺

`starlane-regression` 的描述应该直接说明它支持什么，也说明它不支持什么。

当前描述方向：

```text
Use when the user has data and variable mappings and wants to run Starlane's supported regression delivery workflow. Python and Stata are selectable execution backends. If the user does not specify a backend, ask them to choose before running. The workflow first produces a combination summary table, then waits for the user to choose a candidate row, then produces the final regression output and exact source code used.
```

中文表达：

```text
当用户已有数据和变量映射，并希望运行 Starlane 当前支持的回归交付工作流时使用。Python 和 Stata 是可选执行后端；如果用户没有指定，先询问用户。工作流先生成模型组合汇总表，再等待用户选择候选行，最后输出最终回归结果和精确源码。
```

## 与完整全链路的关系

Starlane 未来可以覆盖四个阶段：

```text
starlane-topic      制定主题
starlane-data       收集清理数据
starlane-regression 建模回归分析
starlane-writing    落文章
```

但当前不应同时实现四个阶段。

当前最重要的是把 `starlane-regression` 做实。第三阶段稳定后，其他阶段只是围绕它补输入、补输出和补上下游 workflow。

## README 的处理原则

README 不应该写成调研流水账。

README 最终应该只保留：

- 项目一句话定位
- 当前支持阶段
- 当前可用 skill
- 当前能力边界
- 最小使用方式
- 指向详细文档的链接

调研、对比、取舍、历史分析应该放在 `docs/research/` 下的独立 Markdown 中。

## 后续需要 Grilling 的问题

后续需要继续做减法，重点确认：

- 第一版是否只保留一个 `starlane-regression` skill
- 是否长期保留 Python 和 Stata 两个后端
- Python 后端的脚本命名和 CLI 入口
- 哪些输出必须作为第一版稳定契约
- `combination_summary.csv` 的列是否已经足够
- 如何表达 `score`，避免被理解成制造显著性
- Stata 后端是否应该执行最终 `.do`，还是只生成 `.do`
- 哪些内容属于 regression 阶段，哪些必须留给未来 writing 阶段
