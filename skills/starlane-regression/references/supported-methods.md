# Supported Methods

`starlane-regression` supports only the regression delivery workflow defined by this skill.

## Supported

- Baseline fixed-effect regressions.
- Control-variable subset enumeration.
- VCE enumeration: OLS, robust, one-way clustered by `panelvar`, two-way clustered by `panelvar` and `timevar`.
- Robustness checks: alternative X, alternative Y, ln(X), ln(Y), lagged X, and time-window sample.
- IV checks when the user provides instruments.
- Mediation or mechanism variables.
- Moderation variables.
- Discrete-group heterogeneity.
- Descriptive statistics for the final selected model set.
- Combination summary table generation.
- Final result generation from a user-selected candidate row.
- Reproducible source artifact generation for the selected env.
- Python env for the supported section families.
- Stata env with reproducible `.do` generation and Word table export when the local Stata environment supports it.

## Not Supported

- DID.
- Event study.
- RDD.
- PSM.
- SCM.
- DML.
- Causal forest.
- Bayesian models.
- Survival analysis.
- Oaxaca decomposition.
- Quantile treatment effects.
- Automatic data sourcing.
- Automatic topic creation.
- Full paper ghostwriting.
- Claims that results are guaranteed to be significant.

If the user asks for an unsupported method, say it is outside the current Starlane contract and do not improvise a new method.
