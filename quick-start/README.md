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

The demo auto-picks the top-scored row of `combination_summary.csv` as the
final-stage candidate. That shortcut exists only so the demo can run
unattended; in the real workflow the candidate row is confirmed with the user,
not chosen by score alone.

## Setup

From the repository root:

```bash
uv sync --project skills/starlane-regression
```

## Run The Python Env

```bash
uv run --project skills/starlane-regression python quick-start/run_demo.py --env python
```

This is also the default:

```bash
uv run --project skills/starlane-regression python quick-start/run_demo.py
```

## Run The Stata Env

Install Stata locally, then run:

```bash
uv run --project skills/starlane-regression python quick-start/run_demo.py --env stata
```

If Stata is not on your `PATH`, set `STARLANE_STATA_BIN`:

```bash
STARLANE_STATA_BIN=/Applications/Stata/StataMP.app/Contents/MacOS/stata-mp \
  uv run --project skills/starlane-regression python quick-start/run_demo.py --env stata
```

## Run Both Envs

```bash
uv run --project skills/starlane-regression python quick-start/run_demo.py --env both
```

`both` runs the Python env and then the Stata env. It does not compare their
results.

## Outputs

The demo calls the same `run_stage.py` pipeline the skill uses, so results are
published to the same per-env directories:

```text
output/starlane-regression/python/combination_summary.csv
output/starlane-regression/python/generated_regression.py
output/starlane-regression/python/final_result.csv
output/starlane-regression/python/final_result.md
output/starlane-regression/python/final_result.docx
```

Typical Stata env outputs:

```text
output/starlane-regression/stata/combination_summary.csv
output/starlane-regression/stata/generated_regression.do
output/starlane-regression/stata/final_result.docx
```

Internal run evidence (inputs, generated sources, logs, manifests) is kept
under `.starlane/runtime/starlane-regression/runs/<run-id>/`.
