# Agent Language Style

Use research-language explanations before implementation details.

Prefer:

```text
The target dataset is firm-year, so firm_id + year should identify each row.
```

Over:

```text
The primary key is invalid.
```

When diagnostics fail, use this structure:

```text
What failed:
Evidence:
Why it matters:
Options:
Recommendation:
Confirmation needed:
```

Do not tell the user that the data is correct. Say that it satisfies the stated
checks, and name any remaining limitations.

When recommending a plan change, distinguish low-risk technical fixes from
research judgments.

Low-risk examples:

- trim whitespace in merge keys
- cast IDs to strings on both sides
- parse years as integers

Judgment examples:

- dropping unmatched observations
- aggregating duplicate records
- changing the target observation unit
- winsorizing or trimming outliers
- imputing missing values
