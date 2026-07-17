# Troubleshooting

## Output Missing

Check that the plan has valid input paths and a supported output format.

## Merge Fails Key Validation

For `1:1`, both sides must be unique by key. For `m:1`, the right side must be
unique. For `1:m`, the left side must be unique.

If the duplicate records require a research judgment, do not auto-fix. Explain
the evidence and recommend a choice.

## Match Rate Is Low

Inspect:

- string versus numeric ID types
- leading zeros
- whitespace
- year/date parsing
- source coverage differences
- whether a crosswalk is required

## Critical Missingness Is High

Inspect whether missingness came from source data, recoding, filters, or merge
failure. Do not impute unless the user confirms the method.

## Engine Does Not Support A Needed Operation

Do not patch the output data. State the missing operation and propose adding
engine support as a development task.
