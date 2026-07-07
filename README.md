# Starlane Skills

Starlane Skills 是一组面向实证研究流程的开源 Agent Skills。

项目目标是让 Codex、Claude Code、Cursor 这类 Agent 工具，能够更稳定地辅助用户完成从研究设计、变量映射、回归执行到结果解释的可复现实证分析流程。

当前状态：第一版 skill 骨架已落地。

## 项目范围

第一版优先面向经管类实证研究场景，尤其是本科毕业论文、课程论文中常见的回归分析任务。

第一版默认用户已经有数据，或者至少能提供一份待分析数据，并愿意说明变量在研究中的角色。

第一版只覆盖一个闭环：用户已有数据和变量映射后，运行回归交付工作流，枚举模型组合，生成汇总表，再根据用户选择的候选行输出最终结果和可复现源码。

## 第一版调研文档

见：[docs/research/empirical-analysis-skill-architecture.md](docs/research/empirical-analysis-skill-architecture.md)。

## 第一版架构

```text
skills/
└── starlane-regression/
    ├── references/
    └── scripts/
```

第一版正式 skill 只有 `starlane-regression`。当前先不抽 `_shared`：输入输出契约、支持方法、工作流约定、实证 section schema 和边界说明都放在 `skills/starlane-regression/references/` 内部。等出现第二个稳定 skill 并产生真实复用需求后，再抽共享规范。

新实现删除了旧 password/XOR 选择机制，改为在 `combination_summary.csv` 中暴露明文 `selection_id`、`cv_idx`、`vce_idx` 和 `cv_selected`。Python 和 Stata 是可选执行后端，不是两个独立 workflow。
