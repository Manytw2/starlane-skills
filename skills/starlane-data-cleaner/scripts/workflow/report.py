"""Markdown report rendering for starlane-data-cleaner."""

from __future__ import annotations

from typing import Any


def _fmt_rate(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.1%}"
    except (TypeError, ValueError):
        return str(value)


def render_report(plan: dict[str, Any], diagnostics: dict[str, Any]) -> str:
    target = plan.get("target", {})
    lines: list[str] = ["# Data Cleaning Report", ""]

    lines.extend(
        [
            "## Target Dataset",
            f"- Target unit: {target.get('unit', 'unspecified')}",
            f"- Target key: {', '.join(target.get('key', [])) or 'unspecified'}",
            f"- Status: {diagnostics.get('status', 'unknown')}",
            "",
        ]
    )

    output = diagnostics.get("output", {})
    lines.extend(
        [
            "## Output",
            f"- Path: {output.get('path', 'n/a')}",
            f"- Rows: {output.get('rows', 'n/a')}",
            f"- Columns: {output.get('columns', 'n/a')}",
            f"- Missing required columns: {', '.join(output.get('required_columns_missing', [])) or 'none'}",
            "",
        ]
    )

    key = diagnostics.get("target_key", {})
    lines.extend(
        [
            "## Target Key Diagnostics",
            f"- Columns: {', '.join(key.get('columns', [])) or 'unspecified'}",
            f"- Missing rows: {key.get('missing_rows', 'n/a')}",
            f"- Duplicate rows: {key.get('duplicate_rows', 'n/a')}",
            f"- Unique: {key.get('unique', 'n/a')}",
            "",
        ]
    )

    merges = diagnostics.get("merges", [])
    if merges:
        lines.extend(["## Merge Diagnostics", ""])
        for merge in merges:
            lines.extend(
                [
                    f"### {merge.get('name', 'merge')}",
                    f"- Type: {merge.get('type', 'n/a')}",
                    f"- Keys: {', '.join(merge.get('keys', []))}",
                    f"- Matched: {merge.get('matched', 'n/a')}",
                    f"- Left only: {merge.get('left_only', 'n/a')}",
                    f"- Right only: {merge.get('right_only', 'n/a')}",
                    f"- Left match rate: {_fmt_rate(merge.get('match_rate_left'))}",
                    f"- Row expansion ratio: {merge.get('row_expansion_ratio', 'n/a')}",
                    "",
                ]
            )

    critical = diagnostics.get("critical_variables", {})
    lines.extend(["## Critical Variable Missingness", ""])
    for var, rate in critical.get("missing_rates", {}).items():
        lines.append(f"- {var}: {_fmt_rate(rate)}")
    lines.extend(
        [
            f"- Complete-case rows: {critical.get('complete_case_rows', 'n/a')}",
            f"- Complete-case rate: {_fmt_rate(critical.get('complete_case_rate'))}",
            "",
        ]
    )

    row_flow = diagnostics.get("row_flow", [])
    if row_flow:
        lines.extend(["## Row Flow", ""])
        for item in row_flow:
            lines.append(
                f"- {item.get('step')}: {item.get('rows_before')} -> {item.get('rows_after')}"
                f" ({item.get('reason', 'no reason recorded')})"
            )
        lines.append("")

    failures = diagnostics.get("hard_gate_failures", [])
    lines.extend(["## Hard Gate Status"])
    if failures:
        lines.append("Failed hard gates:")
        for failure in failures:
            lines.append(f"- {failure}")
    else:
        lines.append("All hard gates passed.")
    lines.append("")

    if failures:
        lines.extend(
            [
                "## Recommended Next Action",
                "Revise the cleaning plan for the failed diagnostics. If the next change requires a data-definition or research judgment, explain the options and ask for confirmation before applying it.",
                "",
            ]
        )

    return "\n".join(lines)
