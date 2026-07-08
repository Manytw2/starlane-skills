# Quick Start Demo

This directory contains a small demo dataset and a launcher for trying the
Starlane regression workflow without bringing your own empirical dataset.

The demo uses one shared research-plan configuration and can run it through
either env:

- Python env
- Stata env

Python and Stata are execution envs for the same workflow. They are not
separate workflows, and this demo does not treat one env as a correctness check
for the other.

## Setup

From the repository root:

```bash
uv sync
```

## Run The Python Env

```bash
uv run python quick-start/run_demo.py --env python
```

This is also the default:

```bash
uv run python quick-start/run_demo.py
```

## Run The Stata Env

Install Stata locally, then run:

```bash
uv run python quick-start/run_demo.py --env stata
```

If Stata is not on your `PATH`, set `STARLANE_STATA_BIN`:

```bash
STARLANE_STATA_BIN=/Applications/Stata/StataMP.app/Contents/MacOS/stata-mp \
  uv run python quick-start/run_demo.py --env stata
```

## Run Both Envs

```bash
uv run python quick-start/run_demo.py --env both
```

`both` runs the Python env and then the Stata env. It does not compare their
results.

## Outputs

Generated files are written under:

```text
quick-start/output/
```

Typical Python env outputs:

```text
quick-start/output/python/combination_summary.csv
quick-start/output/python/final/regression_generated.py
quick-start/output/python/final/final_result.csv
quick-start/output/python/final/final_result.md
quick-start/output/python/final/final_result.docx
```

Typical Stata env outputs:

```text
quick-start/output/stata/combination_summary.csv
quick-start/output/stata/final/regression_generated.do
quick-start/output/stata/final/starlane-regression-results.docx
```
