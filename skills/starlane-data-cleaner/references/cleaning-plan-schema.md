# Cleaning Plan Schema

`cleaning_plan.json` is the source of truth for ordinary cleaning runs. The
agent may revise this plan between runs; it must not patch output datasets by
hand.

## Top-Level Fields

```json
{
  "target": {},
  "inputs": [],
  "operations": [],
  "validation": {},
  "output": {}
}
```

## `target`

```json
{
  "unit": "firm-year",
  "key": ["firm_id", "year"],
  "required_vars": ["firm_id", "year", "y", "x"],
  "critical_vars": ["y", "x"]
}
```

- `unit`: human-readable observation unit.
- `key`: columns that should uniquely identify final rows.
- `required_vars`: columns that must exist in final output.
- `critical_vars`: variables whose missingness is reported for analysis use.

## `inputs`

```json
{
  "name": "finance",
  "path": "raw/finance.csv",
  "role": "using",
  "key": ["firm_id", "year"]
}
```

`name` is used by operations. `path` may be absolute or relative to the current
working directory.

## `operations`

Every operation has an `op` field.

### Rename Columns

```json
{
  "op": "rename",
  "dataset": "firm_basic",
  "columns": {"FirmID": "firm_id"}
}
```

### Select Or Drop Columns

```json
{"op": "select", "dataset": "firm_basic", "columns": ["firm_id", "year"]}
{"op": "drop_columns", "dataset": "firm_basic", "columns": ["unused"]}
```

### String Cleaning

```json
{"op": "trim", "dataset": "firm_basic", "columns": ["firm_id"]}
{"op": "lower", "dataset": "firm_basic", "columns": ["city"]}
{"op": "upper", "dataset": "firm_basic", "columns": ["province_code"]}
```

### Type Casting

```json
{
  "op": "cast",
  "dataset": "firm_basic",
  "columns": {"firm_id": "string", "year": "int", "date": "date"}
}
```

Supported types are `string`, `int`, `float`, and `date`.

### ID Padding

```json
{
  "op": "pad",
  "dataset": "firm_basic",
  "columns": {"firm_id": 6}
}
```

### Replace Coded Missing Values

```json
{
  "op": "replace_missing",
  "dataset": "firm_basic",
  "columns": ["y", "x"],
  "values": [-99, -999, ""]
}
```

### Drop Duplicates

```json
{
  "op": "drop_duplicates",
  "dataset": "finance",
  "key": ["firm_id", "year"],
  "method": "keep_first",
  "reason": "same firm-year appears twice after source export"
}
```

Supported methods are `keep_first`, `keep_last`, and `error`.

### Filter Rows

```json
{
  "op": "filter",
  "dataset": "firm_basic",
  "expr": "year >= 2010 and year <= 2020",
  "reason": "analysis window"
}
```

Filter expressions use pandas `DataFrame.query` syntax.

### Append

```json
{
  "op": "append",
  "name": "all_years",
  "datasets": ["part_1", "part_2"]
}
```

### Merge

```json
{
  "op": "merge",
  "name": "merge_finance",
  "left": "firm_basic",
  "right": "finance",
  "type": "m:1",
  "keys": ["firm_id", "year"],
  "unmatched": "keep_left_with_flag"
}
```

Supported merge types are `1:1`, `m:1`, and `1:m`. The engine validates the
required side's key uniqueness before merging.

Supported unmatched policies:

- `keep_left_with_flag`
- `keep_matched`
- `keep_all_with_flag`

### Set Output Dataset

```json
{"op": "set_output", "dataset": "merge_finance"}
```

If omitted, the current dataset after the last operation is used.

## `validation`

```json
{
  "require_unique_target_key": true,
  "max_critical_missing_rate": 0.1,
  "max_unmatched_rate": 0.15,
  "allow_row_expansion": false
}
```

Validation thresholds become hard gates when present.

## `output`

```json
{
  "dataset_name": "analysis_data",
  "formats": ["csv"],
  "directory": "output/starlane-data-cleaner/python"
}
```

Supported formats are `csv` and `dta`.
