# Starlane Skills — Agent 开发规范

本文件写给在这个仓库里做开发和维护的 coding agent，只约束"怎么改这个仓库"，不介绍项目本身：

- 运行 `starlane-regression` 技能：读 `skills/starlane-regression/SKILL.md`（运行侧事实的唯一出处）。
- 项目架构与设计取舍：读 `docs/ARCHITECTURE.md`。本文件不复述架构。
- 命名规范（文件名、变量、缩写词表）：读 `docs/CONVENTIONS.md`（命名事实的唯一出处）。本文件不复述命名细则。

## 验证命令

改动后先同步依赖，再用 demo 做整链验收：

```bash
uv sync --project skills/starlane-regression
uv run --project skills/starlane-regression python quick-start/run_demo.py --env python
```

- Python env 必跑，约 20~90 秒（summary 阶段按核数并行，多核机器更快）；summary 阶段内置 ModelPlan 漂移校验，日志出现 `STARLANE_PLAN_VERIFIED` 才算通过。
- 改动涉及 Stata env 或跨 env 契约时，再跑 `--env stata`（约 5 分钟，需要本地 Stata 或设置 `STARLANE_STATA_BIN`）。
- 跑完检查 `output/starlane-regression/<env>/` 里的发布产物是否符合预期。
- 文档中的行为声明（路径、命令、产物名）写入前必须实测过。

## 修改边界

按职责分层落点，不要跨层写逻辑：

- "该跑什么"（模型枚举、summary 列、候选组合）只改 `scripts/workflow/model_plan.py`。
- "这个 env 怎么跑"只改 `scripts/envs/python/`、`scripts/envs/stata/`。
- 生命周期与发布（run 目录、manifest、公开产物）只改 `scripts/workflow/run_stage.py` 和 `runtime.py`。
- env 脚本只向 `STARLANE_EXPORT` / `STARLANE_TMP` 写文件，不得自行发布到 `output/`。
- `scripts/stata-code-examples/` 仅供人工查看，禁止读取、运行、复制或作为工作流输入。
- 不追求 Python 与 Stata 逐系数一致；不要为了"对齐"强改任一 env 的估计实现。

## 先商量，再动手

下列改动先提出方案并达成一致，不要直接改：

- 契约面：`analysis_plan` schema、regression args 字段、`combination_summary.csv` 列结构、输出目录布局、`STARLANE_*` 环境变量。
- 支持范围：新增或移除模型模块、方法。
- 用户可见承诺：README 的能力清单、边界声明、许可。
- 新增运行依赖或修改 `skills/starlane-regression/pyproject.toml`。

其余改动（bug 修复、不改契约的重构、文档纠错）可直接动手。

提案方法：设计与规范类议题（命名、目录结构、契约形态）先总结问题，再调研成熟项目的既有解法并分析其取舍动机，带出处提案；不闭门造方案。

## 文档同步义务

改了代码就同步文档，每类事实只允许一个权威出处：

- 动作与标准分离：检查清单、gate、登记步骤等 agent 动作指引只写入本文件；标准类文档（`docs/CONVENTIONS.md`、`SKILL.md`、`docs/ARCHITECTURE.md`）只写事实与规范。动作指引混入标准文档即为越界，须挪回本文件。
- 运行侧事实（工作流、命令、产物）的唯一出处是 `SKILL.md`；`references/workflow.md` 只保留模块引导节奏和 env 共享契约，不得复述 `SKILL.md`。
- 改输出路径或发布行为 → 同步 `SKILL.md`、`references/workflow.md`、`docs/ARCHITECTURE.md`、`docs/ARCHITECTURE_EN.md`、`README.md`、`README_EN.md`、`quick-start/README.md`。
- 改模型模块或列契约 → 同步 `references/models/*`、`references/supported-methods.md`、`SKILL.md` 的 description 与 Scope，并保证与 `model_plan.py` 一致。
- 起或改任何名字（文件名、字段、缩写、section/列 token）→ 以 `docs/CONVENTIONS.md` 为准；新增命名约定沉淀回其相应小节。
- 中英双语文档（README、ARCHITECTURE）必须成对更新。成对指事实与结构对齐，不要求逐句直译：README 的定位语与语气差异是有意设计——中文面向传播，口语化、亲民（如带引号的"一键显著"是自嘲式称呼，不是能力承诺）；英文面向学术场景，表述收敛严谨。不要把这种语气差异当作不一致来"修复"。
- 新的踩坑经验和行为约定沉淀回本文件。

## 运行卫生

- 临时文件写系统 temp 或 run 目录的 `tmp/`，用完即清；不要在仓库里散落草稿文件。
- `output/` 与 `.starlane/` 已被 gitignore，不要提交它们的内容。
- runtime 积累过多时用 `scripts/check-starlane-regression-runtime.sh` 查看、`scripts/clean-starlane-regression-runtime.sh` 清理；清理不得删除 `output/starlane-regression/`。
- 并发跑 demo 或 stage 会互相覆盖公开产物（后写为准），验证时避免并行执行。
- 并发起多个 Stata 批处理实例时，必须给每个实例独立的 `STATATMP` 目录，否则 `preserve`/`tempfile` 会互相覆盖（parallel 包 1.14 的老坑）；并发 Python 估计进程要把 BLAS/numba 线程数压到 1 防超订。`summary_parallel.py` 已内置这两条，新增并发路径同样遵守。

## 架构演化

发现结构开始混乱（职责越界、内容重复、文档与行为分叉）时，先停下来发起讨论：给出证据、影响面和候选方案，达成一致后再改。不做静默的大范围重构。
