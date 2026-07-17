# Output Contract

User-facing outputs are written under:

```text
output/starlane-data-cleaner/python/
```

Required outputs:

- `analysis_data.csv` or `analysis_data.dta`
- `cleaning_plan.json`
- `cleaning_diagnostics.json`
- `cleaning_report.md`

When a run fails hard gates, still write diagnostics and report if possible.

The report should summarize:

- target dataset expectation
- input files
- operations performed
- merge diagnostics
- target-key diagnostics
- critical-variable missingness
- row-flow losses
- hard gate pass/fail status
- recommended next action when failed
