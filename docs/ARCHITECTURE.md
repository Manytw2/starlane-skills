# Starlane Skills 架构说明

本文说明 Starlane Skills 当前的项目骨架和主要设计取舍。它面向贡献者和维护者，不是使用教程。

## 项目定位

Starlane Skills 不是一组零散的回归脚本，而是一条由 Agent 引导的实证分析工作流。

当前正式入口只有一个：

```text
skills/starlane-regression/SKILL.md
```

用户可以从数据文件、部分变量映射或研究想法开始。Agent 先把研究设定组织成同一个 `analysis_plan`，再把它编译成执行层需要的回归参数，最后交给 Python 或 Stata 环境完成 summary 和 final 阶段。

## 核心原则

### 一个用户入口

第一版不拆成 `starlane-baseline`、`starlane-robustness`、`starlane-iv` 等多个 skill。

对用户来说，实证分析是一条连续工作流：先确认研究主线，再确认基准回归、稳健性、机制、调节、异质性或 IV 等模块。拆成多个入口会让用户过早处理实现细节，也会让 Agent 更难维护同一个研究计划。

### 一个分析计划

引导模式下，Agent 只维护一个 `analysis_plan_draft`。

工作流应该是：

```text
数据画像 -> 初始化 analysis_plan_draft -> 分模块确认 -> review 同一个 draft -> 编译回归参数 -> 执行
```

不应该是：

```text
分模块聊天 -> 另写一份自然语言计划 -> 再写一份结构化计划 -> 执行
```

`analysis_plan` 是研究层表达，回归参数是执行层表达。用户确认研究设定时，应尽量使用“被解释变量”“核心解释变量”“机制变量”等研究语言，而不是要求用户直接填写 `y`、`x`、`meds` 这类后端字段。

### Python 和 Stata 是 env

Python 和 Stata 是两种执行环境，不是两条用户工作流。

它们共享：

- `analysis_plan` schema
- 支持的模型模块
- summary / final 阶段契约
- 候选设定选择标识
- 输出物清单
- 研究语言和解释边界

它们可以不同：

- 估计器包和默认设置
- 固定效应吸收方式
- 标准误修正细节
- 缺失值处理的包默认行为
- 生成源码的形态
- 表格导出方式
- runtime、依赖和日志证据

项目不追求 Python 和 Stata 逐系数完全一致。更重要的是：同一条 workflow、同一个研究计划、符合各自生态习惯的可复现源码，以及清楚披露估计选择。

## 工作流

```text
用户提供数据或变量映射
-> 生成数据画像
-> Agent 说明变量推断边界
-> 初始化 analysis_plan_draft
-> 确认研究主线和模型模块
-> review 同一个 analysis_plan_draft
-> 保存确认后的 analysis_plan
-> 编译成 regression args
-> summary stage 生成 combination_summary.csv
-> 用户选择或确认候选设定
-> final stage 生成最终输出和源码
```

summary 阶段负责枚举候选设定。每套候选设定包含一套共享控制变量组合、一种标准误处理方式，以及所有启用模型模块在这套设定下的结果。它输出的 `combination_summary.csv` 是决策辅助材料，不是自动最终结论。

final 阶段使用用户确认的候选行，生成最终回归输出和可复现源码。

## 关键契约

### `analysis_plan`

`analysis_plan` 按研究模块组织，代表用户确认后的研究设定。它通常包含：

```text
data
research
baseline
robustness
mechanism
moderation
heterogeneity
iv
execution
```

完整 schema 见：

```text
skills/starlane-regression/references/analysis-plan-schema.md
```

### regression args

regression args 是脚本执行层的参数合同，由 `analysis_plan` 编译而来。它不是用户侧主要交互模型。

编译入口：

```text
uv run --project skills/starlane-regression python skills/starlane-regression/scripts/workflow/run_stage.py compile ...
```

### 候选设定选择

summary 阶段输出：

```text
output/starlane-regression/<env>/combination_summary.csv
```

其中：

- `selection_id` 是明文候选标识
- `cv_idx` 标识控制变量子集
- `vce_idx` 标识标准误选择
- `cv_selected` 记录选中的控制变量
- `score` 是方向感知的显著性辅助评分

`score` 只能帮助排序和筛选，不能替代研究判断。

### Runtime 与 Output 分层

Starlane 区分用户可见成果和内部运行证据：

```text
output/starlane-regression/
  python/
    combination_summary.csv
    final_result.docx
    regression_generated.py
    ...
  stata/
    combination_summary.csv
    regression_generated.do
    starlane-regression-results.docx

.starlane/runtime/starlane-regression/runs/<run-id>/
  inputs/
  generated/
  logs/
  outputs/
  tmp/
  run.json
```

`output/starlane-regression/<env>/` 是用户查看结果的入口，按 env 分目录避免同名产物互相覆盖。`.starlane/runtime/` 是 Agent 和开发者排查问题的内部目录，默认被 Git 忽略。

Python 和 Stata env 只负责执行 summary/final 逻辑。外层编排入口 `scripts/workflow/run_stage.py` 负责创建 run 目录、写 manifest、设置 `STARLANE_EXPORT` 和 `STARLANE_TMP`、校验 summary 表头与 ModelPlan 一致、在成功后发布 public output 并清理 `tmp/`。分块 summary 跑（`--cv-idx-start/--cv-idx-end`）属于中间产物，不发布。

summary 阶段由 `scripts/workflow/summary_parallel.py` 统一编排：按机器核数、可用内存和任务数自动决定并发度，把 cv 子集区间按 guided self-scheduling（块大小递减）切块，Python env 起多个 `summary.py --cv-idx-start/end` 子进程、Stata env 起多个 `stata -b` 批处理实例，最后合并 part 表、校验 `selection_id` 唯一性并按 `score` 降序写出 `combination_summary.csv`。串行只是并发度为 1 的退化情形，没有独立代码路径。两条并发纪律：每个 Stata worker 使用独立 `STATATMP` 子目录（并发实例共享 tempfile 目录会互相覆盖 preserve/tempfile）；每个 Python worker 限制 BLAS/numba 线程为 1，避免进程级并行之上再叠线程超订。xlsx/xls 输入会先做一次预热缓存（Stata 转 `.dta`，Python 转 `.pkl`），避免每个 worker 重复解析慢格式。

成功运行后不保留 `.score_*.dta` 这类低价值中间文件。失败运行会保留 logs 和 tmp，方便诊断。

## 目录结构

```text
skills/starlane-regression/
  SKILL.md
  references/
    workflow.md
    agent-language-style.md
    analysis-plan-schema.md
    supported-methods.md
    output.md
    troubleshooting.md
    models/
      baseline.md
      robustness.md
      mechanism.md
      moderation.md
      heterogeneity.md
      iv.md
  scripts/
    workflow/
      run_stage.py
      summary_parallel.py
      contracts.py
      model_plan.py
      stata_emit.py
      verify_model_plan_drift.py
      profile_data.py
      compile_plan_to_regression_args.py
      runtime.py
    envs/
      python/
      stata/
```

主要职责：

- `SKILL.md`：Agent 入口，说明适用场景、必须读取的 reference、执行边界。
- `references/workflow.md`：共享工作流和 env 契约。
- `references/agent-language-style.md`：用户沟通语言和变量推断边界。
- `references/analysis-plan-schema.md`：研究计划结构。
- `references/models/`：各模型模块的引导方式、plan 字段、section schema 和解释边界。
- `references/output.md`：输出物和表格规范。
- `references/troubleshooting.md`：常见失败场景和处理方式。
- `scripts/workflow/run_stage.py`：统一编排入口，负责 profile/compile/summary/final 各阶段与发布。
- `scripts/workflow/summary_parallel.py`：summary 阶段的分块并行编排（并发度探测、guided 切块、worker 进程池、part 合并与排序）。
- `scripts/workflow/contracts.py`：regression args 和候选选择的 JSON 契约校验。
- `scripts/workflow/model_plan.py`：模型枚举的单一事实来源，回答"该跑什么"。
- `scripts/workflow/stata_emit.py`：把 ModelPlan 渲染成 Stata 配置。
- `scripts/workflow/verify_model_plan_drift.py`：校验 summary 产物与 ModelPlan 是否漂移。
- `scripts/workflow/` 其余：数据画像、plan 编译和 runtime 生命周期管理。
- `scripts/envs/`：Python / Stata 的 summary、final 和源码生成逻辑，回答"这个 env 怎么跑"。

仓库顶层还有两个辅助目录：

- `quick-start/`：demo 数据和薄壳启动器，直接复用 `run_stage.py` 管线。
- `scripts/`（仓库根）：runtime 清理与状态检查脚本，以及 `stata-code-examples/`（仅供人工查看的示例代码，Agent 不得将其作为工作流输入）。

## 设计取舍

### 暂不抽 `_shared`

当前只有一个稳定 skill：`starlane-regression`。共享规范先放在它自己的 `references/` 内部。等出现第二个稳定 skill，并且产生真实复用需求后，再抽共享层。

### 不保留旧顶层 wrapper

当前执行入口按职责放在：

```text
scripts/workflow/
scripts/envs/python/
scripts/envs/stata/
```

Agent 文档、运行说明和测试都应该使用这些路径，不再引用旧的顶层 wrapper。

### 不把显著性当目标函数

Starlane 会枚举模型组合，也会给出辅助评分，但它不是显著性工厂。

模型选择应同时考虑理论合理性、变量定义、样本量、缺失情况、标准误选择、稳健性方向和解释边界。Agent 必须保留复现材料，并明确区分统计相关和因果识别。
