# starlane-data-cleaner Workflow

This reference defines the user workflow and execution contract for
`starlane-data-cleaner`.

## Core Rhythm

```text
profile -> draft or revise cleaning_plan -> run -> validate -> report
```

The loop modifies `cleaning_plan.json`, not the engine code. The Python engine
is a stable interpreter for supported operations.

## Stage Commands

```text
uv run --project skills/starlane-data-cleaner python scripts/workflow/run_stage.py profile --inputs-json <inputs-json>
uv run --project skills/starlane-data-cleaner python scripts/workflow/run_stage.py run --plan <cleaning-plan-json>
uv run --project skills/starlane-data-cleaner python scripts/workflow/run_stage.py validate --plan <cleaning-plan-json> --data <output-data>
```

## Stage Responsibilities

- `profile`: read declared input files and summarize rows, columns, types,
  missingness, and duplicate-key diagnostics when keys are provided.
- `run`: execute the plan from raw inputs, write user-facing outputs, validate
  the result, and generate a Markdown report.
- `validate`: inspect an existing output against plan expectations.

## Agent Loop

After every run:

1. Read `cleaning_diagnostics.json`.
2. If hard gates pass, explain the result and deliver output paths.
3. If hard gates fail and the next correction is a supported plan change,
   revise `cleaning_plan.json` and rerun.
4. If the next correction requires judgment, guide the user:
   - state what failed
   - show evidence
   - explain why it matters
   - list feasible options
   - recommend one option with tradeoffs
   - ask for confirmation

## Runtime And Output

User-facing outputs are written under:

```text
output/starlane-data-cleaner/python/
```

The first implementation keeps runtime lightweight. It writes reproducibility
fields into diagnostics and copies the final plan into the public output
directory.
