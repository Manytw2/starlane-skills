<div align="center">

# Starlane Skills

### Reproducible regression workflows for empirical research

From research ideas to executable analysis plans.

[![license](https://img.shields.io/badge/license-PolyForm%20Noncommercial%201.0.0-green)](LICENSE.md)
[![install](https://img.shields.io/badge/install-Codex%20%7C%20Claude%20Code%20%7C%20Cursor-black)](#quick-start)
[![skills](https://img.shields.io/badge/skills-1-blue)](skills/starlane-regression/SKILL.md)
[![language](https://img.shields.io/badge/language-English%20%7C%20中文-blue)](README.md)

[Quick Start](#quick-start) · [Architecture](docs/ARCHITECTURE_EN.md) · [中文](README.md)

</div>

An Agent Skill for turning empirical research ideas into reproducible regression workflows.

Starlane helps with the coding and workflow burden behind empirical analysis: model setup, combination search, result tables, and reproducibility artifacts. It does not manufacture significance, conclusions, or research designs.

## What It Does

![Starlane workflow](assets/starlane-workflow.png)

The current release provides one production skill: `starlane-regression`.

It is designed for common empirical-analysis workflows in economics, finance, management, and related social-science projects. Starting from a data file and a research idea, the skill guides the user through an analysis plan, enumerates supported model combinations, helps select a candidate result, and generates final outputs with reproducible source code.

The first version focuses on:

- data profiling and variable-role suggestions
- baseline regressions, control-variable search, and standard-error choices
- robustness checks, mechanism checks, moderation, heterogeneity, and IV-related checks
- Python and Stata execution environments
- candidate summary tables, final regression output, run notes, and reproducible source code

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

To see what the repository produces without bringing your own data, run the built-in demo:

```bash
uv sync
uv run python quick-start/run_demo.py --env python
```

You can also run the Stata env:

```bash
uv run python quick-start/run_demo.py --env stata
```

## Developer Setup

```bash
git clone https://github.com/Manytw2/starlane-skills.git
cd starlane-skills
uv sync
```

Run Python scripts through `uv run python ...`.

## Project Layout

```text
skills/
└── starlane-regression/
    ├── SKILL.md
    ├── references/
    └── scripts/
```

`SKILL.md` is the Agent entrypoint. `references/` contains workflow, model-module, output, and troubleshooting guidance. `scripts/` contains data profiling, plan compilation, and Python / Stata execution scripts.

## Documentation

- [Architecture](docs/ARCHITECTURE_EN.md)
- [架构说明](docs/ARCHITECTURE.md)
- [中文 README](README.md)

## Boundaries

Starlane is an empirical-analysis assistant, not a thesis-writing tool or a significance factory.

It keeps variable mappings, model choices, generated source code, and run notes explicit so results can be reproduced. The user remains responsible for the research question, variable definitions, model interpretation, and any causal claims.

## License

This project is licensed under the [PolyForm Noncommercial License 1.0.0](LICENSE.md). Noncommercial use is permitted. Commercial use requires separate permission.
