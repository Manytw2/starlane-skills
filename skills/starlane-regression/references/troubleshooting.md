# Troubleshooting

Common issues:

- `r(601)`: input file path is wrong.
- `r(111)`: a mapped variable does not exist.
- `r(109)`: a numeric operation was applied to a string variable.
- `r(198)`: argument order or option value is invalid.
- `reghdfe` missing: run `ssc install reghdfe`.
- `ivreghdfe` missing: run `ssc install ivreghdfe`.
- `reg2docx` or `sum2docx` missing: install the required Stata export package before running the generated final `.do`.

If summary generation succeeds but final generation fails, check that the same 18 arguments were reused and that `cv_idx` and `vce_idx` came from the same `combination_summary.csv`.
