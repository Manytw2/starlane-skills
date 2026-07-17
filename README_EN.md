<div align="center">

# Starlane Skills

### Reproducible regression workflows for empirical research

From research ideas to executable analysis plans.

[![license](https://img.shields.io/badge/license-PolyForm%20Noncommercial%201.0.0-green)](LICENSE.md)
[![install](https://img.shields.io/badge/install-Codex%20%7C%20Claude%20Code%20%7C%20Cursor-black)](#quick-start)
[![skills](https://img.shields.io/badge/skills-2-blue)](skills/starlane-regression/SKILL.md)
[![language](https://img.shields.io/badge/language-English%20%7C%20中文-blue)](README.md)

[Quick Start](#quick-start) · [Architecture](docs/ARCHITECTURE_EN.md) · [中文](README.md)

</div>

An Agent Skill for turning empirical research ideas into reproducible regression workflows.

Starlane helps with the coding and workflow burden behind empirical analysis: model setup, combination search, result tables, and reproducibility artifacts. It does not manufacture significance, conclusions, or research designs.

![Starlane workflow](assets/starlane-workflow.png)

## Skill Index

The following skills under `skills/` can be invoked:

| Skill | Status | Purpose | Trigger |
| --- | --- | --- | --- |
| [`starlane-regression`](skills/starlane-regression/SKILL.md) | Stable | Regression workflow for empirical research in economics and management: data profiling, guided analysis planning, candidate-combination enumeration and scoring, final regression output with reproducible source code, Python / Stata execution envs | `/starlane-regression`, or describe needs such as "regression analysis", "baseline regression", or "robustness checks" |
| [`starlane-data-cleaner`](skills/starlane-data-cleaner/SKILL.md) | Stable | Data cleaning and merge workflow for economics and management research: data profiling, parameterized cleaning plans, stable Python execution, key/merge/missingness/row-flow diagnostics, and cleaning reports | `/starlane-data-cleaner`, or describe needs such as "clean data", "merge data", or "construct analysis dataset" |

## Quick Start

Install:

```bash
npx skills@latest add Manytw2/starlane-skills
```

Then invoke the skill in an Agent environment that supports Skills:

```text
/starlane-regression
```

You can start from a data file and a rough research idea, or provide complete variable mappings directly. The Agent confirms the research setup before compiling it into executable regression arguments.

For data cleaning or merging, invoke:

```text
/starlane-data-cleaner
```

This skill first confirms the target observation unit, keys, required variables, and merge relationships. It then generates or revises `cleaning_plan.json`, runs a stable engine, and checks key uniqueness, merge matching, sample loss, and critical-variable missingness.

To see what the repository produces without bringing your own data, run the built-in demo:

```bash
uv sync --project skills/starlane-regression
uv run --project skills/starlane-regression python quick-start/run_demo.py --env python
```

Data-cleaning demo:

```bash
uv sync --project skills/starlane-data-cleaner
uv run --project skills/starlane-data-cleaner python quick-start/data-cleaner/run_demo.py
```

You can also run the Stata env:

```bash
uv run --project skills/starlane-regression python quick-start/run_demo.py --env stata
```

After a run completes, user-facing results are written to `output/starlane-regression/<env>/`.

## Developer Setup

```bash
git clone https://github.com/Manytw2/starlane-skills.git
cd starlane-skills
uv sync --project skills/starlane-regression
uv sync --project skills/starlane-data-cleaner
```

Each skill declares its runtime environment inside its own directory. Run Python scripts through `uv run --project skills/<skill-name> python ...` instead of relying on the current workspace Python environment.

## Project Layout

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

`SKILL.md` is the Agent entrypoint. `references/` contains workflow, contract, output, and troubleshooting guidance. `scripts/` contains profiling, plan execution, diagnostics, and env-specific scripts.

## Documentation

- [Architecture](docs/ARCHITECTURE_EN.md)
- [架构说明](docs/ARCHITECTURE.md)
- [中文 README](README.md)

## Boundaries

Starlane is an empirical-analysis assistant, not a thesis-writing tool or a significance factory.

It keeps variable mappings, model choices, generated source code, and internal run evidence explicit so results can be reproduced. The user remains responsible for the research question, variable definitions, model interpretation, and any causal claims.

## License

This project is licensed under the [PolyForm Noncommercial License 1.0.0](LICENSE.md). Noncommercial use is permitted. Commercial use requires separate permission.
