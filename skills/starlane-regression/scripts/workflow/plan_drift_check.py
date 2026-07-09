"""Verify summary artifacts still match the canonical ModelPlan."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from contracts import load_regression_args_json
from model_plan import RegressionArgsProxy, build_model_plan


def read_header(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        return next(reader, [])


def summary_header_problems(args_values: dict[str, str], summary_csv: str | Path) -> list[str]:
    expected = list(build_model_plan(RegressionArgsProxy(args_values)).summary_columns)
    actual = read_header(Path(summary_csv))
    if actual == expected:
        return []
    problems = [
        "ModelPlan drift detected: summary header does not match canonical plan.",
        f"Expected {len(expected)} columns; got {len(actual)}.",
    ]
    for idx, (left, right) in enumerate(zip(expected, actual)):
        if left != right:
            problems.append(f"First mismatch at column {idx}: expected {left!r}, got {right!r}")
            break
    if len(expected) != len(actual):
        problems.append(f"Expected tail: {expected[len(actual):len(actual) + 5]!r}")
        problems.append(f"Actual tail: {actual[len(expected):len(expected) + 5]!r}")
    return problems


def check_summary_header(args_values: dict[str, str], summary_csv: str | Path) -> int:
    """Raise if the summary CSV header drifted from the canonical ModelPlan."""
    problems = summary_header_problems(args_values, summary_csv)
    if problems:
        raise ValueError("\n".join(problems))
    return len(read_header(Path(summary_csv)))


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify summary CSV header matches ModelPlan.")
    parser.add_argument("--args-json", required=True)
    parser.add_argument("--summary-csv", required=True)
    ns = parser.parse_args()

    args_values = load_regression_args_json(ns.args_json)
    problems = summary_header_problems(args_values, ns.summary_csv)
    if problems:
        for line in problems:
            print(line, file=sys.stderr)
        return 1
    print(f"ModelPlan header verified: {len(read_header(Path(ns.summary_csv)))} columns.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
