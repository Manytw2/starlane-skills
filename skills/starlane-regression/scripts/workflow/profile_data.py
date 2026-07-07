"""Create a Starlane data profile for guided regression setup."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def read_data(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".dta":
        return pd.read_stata(path, convert_categoricals=False)
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in (".xls", ".xlsx"):
        return pd.read_excel(path)
    raise ValueError(f"Unsupported input format: {path}")


def clean_number(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        if not math.isfinite(float(value)):
            return None
        return float(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    return value


def numeric_summary(series: pd.Series) -> dict[str, Any]:
    values = pd.to_numeric(series, errors="coerce")
    nonmissing = values.dropna()
    if nonmissing.empty:
        return {}
    return {
        "min": clean_number(nonmissing.min()),
        "max": clean_number(nonmissing.max()),
        "mean": clean_number(nonmissing.mean()),
        "std": clean_number(nonmissing.std()),
    }


def variable_profile(df: pd.DataFrame) -> list[dict[str, Any]]:
    total = len(df)
    rows: list[dict[str, Any]] = []
    for name in df.columns:
        series = df[name]
        nonmissing = int(series.notna().sum())
        missing = total - nonmissing
        unique = int(series.nunique(dropna=True))
        row: dict[str, Any] = {
            "name": str(name),
            "dtype": str(series.dtype),
            "nonmissing": nonmissing,
            "missing": missing,
            "missing_rate": clean_number(missing / total if total else 0),
            "unique": unique,
        }
        if pd.api.types.is_numeric_dtype(series):
            row.update(numeric_summary(series))
        rows.append(row)
    return rows


def candidate_names(df: pd.DataFrame) -> dict[str, list[str]]:
    names = [str(c) for c in df.columns]
    lower = {name: name.lower() for name in names}

    entity_keywords = ("id", "firmid", "firm_id", "companyid", "company_id", "code", "stkcd")
    time_keywords = ("year", "yr", "date", "time")
    entity = [name for name in names if lower[name] in entity_keywords or lower[name].endswith("id")]
    time = [name for name in names if lower[name] in time_keywords or "year" in lower[name]]

    binary: list[str] = []
    for name in names:
        unique_values = df[name].dropna().unique()
        if 0 < len(unique_values) <= 2:
            binary.append(name)

    log_named = [name for name in names if lower[name].startswith("ln")]

    return {
        "panel_entity": entity,
        "panel_time": time,
        "binary": binary,
        "log_named": log_named,
    }


def warnings_for(profile: list[dict[str, Any]]) -> list[str]:
    warnings: list[str] = []
    for row in profile:
        missing_rate = float(row.get("missing_rate") or 0)
        if missing_rate >= 0.1:
            warnings.append(f"{row['name']} has missing_rate >= 10% ({missing_rate:.1%})")
    return warnings


def build_profile(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")
    df = read_data(path)
    variables = variable_profile(df)
    candidates = candidate_names(df)
    return {
        "input_path": str(path),
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "variables": variables,
        "panel_candidates": {
            "entity": candidates["panel_entity"],
            "time": candidates["panel_time"],
        },
        "binary_candidates": candidates["binary"],
        "log_named_candidates": candidates["log_named"],
        "warnings": warnings_for(variables),
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a Starlane data profile JSON file.")
    parser.add_argument("input_path", help="Input data file: .dta, .csv, .xlsx, or .xls")
    parser.add_argument("--output", "-o", help="Output JSON path. Defaults to stdout.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv or sys.argv[1:])
        profile = build_profile(Path(args.input_path))
        text = json.dumps(profile, ensure_ascii=False, indent=2)
        if args.output:
            out = Path(args.output)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text + "\n", encoding="utf-8")
            print(f"STARLANE_PROFILE_OUTPUT: {out}")
        else:
            print(text)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
