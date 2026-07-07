# Starlane Tests

This directory contains project-level regression workflow tests.

Test code files use snake_case because they are machine-facing code assets.

The demo backend test uses `/Users/daydream/Desktop/demo.dta` when available.

The target test shape is:

```text
stage 1: summary table
stage 2: generated source artifact
stage 3: run generated source artifact and produce Word output
```

For backend parity, compare stage 1 outputs and stage 3 Word outputs for the same selected `cv_idx` and `vce_idx`. Stage 2 source files are backend-specific and should be checked for existence and reproducibility, not byte-level equality.

The demo smoke test intentionally uses `cv_idx_start=0` and `cv_idx_end=1`, so it produces only 2 control-subset chunks * 4 VCE choices = 8 rows. That is not the full enumeration. For the current demo mapping, full enumeration is 31 control-subset choices * 4 VCE choices = 124 rows.
