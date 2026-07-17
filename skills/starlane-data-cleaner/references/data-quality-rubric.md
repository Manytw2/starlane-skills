# Data Quality Rubric

After every run, inspect diagnostics before declaring success.

## Hard Gates

The first implementation treats these as hard gates:

- raw input files were not modified
- output dataset exists and is readable
- required columns exist
- target key columns exist
- target key has no missing values
- target key is unique in final output when configured
- every merge reports matched, left-only, and right-only counts
- merge does not create unexpected row expansion when configured
- every drop or filter operation has a recorded reason
- critical variable missingness is reported
- output can be regenerated from plan and raw inputs

Configured thresholds may add hard gates:

- left-side merge unmatched rate is below `max_unmatched_rate`
- critical variable missingness is below `max_critical_missing_rate`
- output row count is within an expected range
- numeric values are inside configured ranges

## Diagnostic Groups

### Structure

- output path
- row count
- column count
- missing required columns
- empty columns

### Target Key

- key columns
- key missing rows
- duplicate key rows
- uniqueness status

### Merge

For every merge:

- merge type
- keys
- left rows before
- right rows before
- rows after
- matched rows
- left-only rows
- right-only rows
- left match rate
- row expansion ratio

### Row Flow

For every filter, duplicate drop, append, or merge:

- rows before
- rows after
- rows added or dropped
- drop rate when applicable
- reason when rows are dropped

### Critical Variables

- missing rate by critical variable
- complete-case row count
- complete-case rate

### Reproducibility

- input paths
- input file hashes
- plan path
- output paths
- report path
- raw files unchanged

## User Judgment Cases

Do not guess silently when diagnostics require judgment. Guide the user through:

- duplicate target keys
- low match rates with multiple possible causes
- whether to keep or drop unmatched observations
- whether to aggregate duplicate records
- whether to winsorize outliers
- whether to impute missing values
- conflicting values across sources
- changing the analysis sample boundary
