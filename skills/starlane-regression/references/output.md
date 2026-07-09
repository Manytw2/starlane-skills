# Table Output Standard

This reference defines the first Starlane table-output direction.

## Current State

The Python env currently writes Word output using `python-docx`.

The Stata env writes Word output through generated Stata code and `reg2docx`/`sum2docx` when available.

The two outputs are not required to be byte-for-byte identical in the current version.

## Standard Goal

Starlane tables should be readable for undergraduate economics and management empirical papers.

Tables should include:

- coefficient with significance stars
- standard errors in parentheses
- observations
- R-squared when available
- fixed-effect indicators
- clear model titles
- clear notes for significance levels and standard errors
- source and reproducibility context outside the main coefficient table when relevant

## Current Constraint

Do not claim that the current Python Word output matches Stata `reg2docx`.

Do not claim that it matches any specific journal template.

## Future Work

Future table work should separately investigate empirical table conventions in leading journals, then create Starlane table profiles.

Likely future profiles:

- undergraduate thesis default
- management journal style
- economics journal style
- finance journal style

This should be implemented through a renderer, not by putting large table-format instructions in `SKILL.md`.
