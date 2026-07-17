<div align="center">

# Starlane Skills

### 帮你“一键显著”的 Agent Skill

你来提供想法，我们帮你实现

[![license](https://img.shields.io/badge/license-PolyForm%20Noncommercial%201.0.0-green)](LICENSE.md)
[![install](https://img.shields.io/badge/install-Codex%20%7C%20Claude%20Code%20%7C%20Cursor-black)](#快速开始)
[![skills](https://img.shields.io/badge/skills-2-blue)](skills/starlane-regression/SKILL.md)
[![language](https://img.shields.io/badge/language-中文%20%7C%20English-blue)](README_EN.md)

[立即安装](#快速开始) · [架构说明](docs/ARCHITECTURE.md) · [English](README_EN.md)

</div>

Starlane Skills 关注的是把实证分析里的代码、模型枚举、结果整理和复现材料自动化；它不会替你捏造结论，也不会把不显著的结果包装成显著。

![Starlane workflow](assets/starlane-workflow.png)

## 技能索引

当前 `skills/` 下包含以下可触发技能：

| 技能 | 状态 | 用途 | 触发方式 |
| --- | --- | --- | --- |
| [`starlane-regression`](skills/starlane-regression/SKILL.md) | Stable | 经管类实证回归工作流：数据画像、引导式研究计划、候选设定枚举与评分汇总、最终回归输出和可复现源码，支持 Python / Stata 双执行环境 | `/starlane-regression`，或描述"回归分析""基准回归""稳健性检验"等需求 |
| [`starlane-data-cleaner`](skills/starlane-data-cleaner/SKILL.md) | Stable | 经管类数据清洗和合并工作流：数据画像、参数化清洗计划、稳定 Python 执行器、key/merge/缺失/样本流失诊断和清洗报告 | `/starlane-data-cleaner`，或描述"洗数据""合并数据""构造分析数据集"等需求 |

## 快速开始

安装：

```bash
npx skills@latest add Manytw2/starlane-skills
```

然后在支持 Skills 的 Agent 工具中调用：

```text
/starlane-regression
```

你可以从一份数据文件和一个研究想法开始，也可以直接提供已经整理好的变量映射。Agent 会先和你确认研究设定，再把确认后的计划编译成可执行的回归任务。

如果要清洗或合并数据，可以调用：

```text
/starlane-data-cleaner
```

这个技能会先确认目标数据集的观测单位、key、必需变量和合并关系，再生成或调整 `cleaning_plan.json`，用稳定执行器运行，并检查 key 唯一性、merge 匹配情况、样本流失和关键变量缺失。

如果你只是想先看这个仓库会跑出什么，可以使用内置 demo：

```bash
uv sync --project skills/starlane-regression
uv run --project skills/starlane-regression python quick-start/run_demo.py --env python
```

数据清洗 demo：

```bash
uv sync --project skills/starlane-data-cleaner
uv run --project skills/starlane-data-cleaner python quick-start/data-cleaner/run_demo.py
```

也可以选择 Stata env：

```bash
uv run --project skills/starlane-regression python quick-start/run_demo.py --env stata
```

运行完成后，用户可见结果会写入 `output/starlane-regression/<env>/`。

## 开发者安装

```bash
git clone https://github.com/Manytw2/starlane-skills.git
cd starlane-skills
uv sync --project skills/starlane-regression
uv sync --project skills/starlane-data-cleaner
```

每个 skill 的运行环境声明在各自目录内。Python 脚本请通过 `uv run --project skills/<skill-name> python ...` 执行，不要依赖当前业务项目的 Python 环境。

## 项目结构

```text
skills/
├── starlane-regression/
│   ├── SKILL.md
│   ├── references/
│   └── scripts/
└── starlane-data-cleaner/
    ├── SKILL.md
    ├── references/
    └── scripts/
```

`SKILL.md` 是 Agent 入口；`references/` 放工作流、契约、输出规范和故障处理说明；`scripts/` 放数据画像、计划执行、诊断以及各执行环境脚本。

## 文档

- [架构说明](docs/ARCHITECTURE.md)
- [Architecture](docs/ARCHITECTURE_EN.md)
- [English README](README_EN.md)

## 边界

Starlane 是实证分析助手，不是论文代写工具，也不是显著性工厂。

它会保留变量映射、模型选择、生成代码和内部运行证据，帮助你复现结果；但研究问题是否成立、变量定义是否合理、模型解释是否可以支持因果结论，仍然需要你判断。

## 许可

本项目采用 [PolyForm Noncommercial License 1.0.0](LICENSE.md)。你可以将它用于非商业目的；商业使用需要单独授权。
