"""Diagnostics builders for the Python cleaner env."""

from __future__ import annotations

from typing import Any

import pandas as pd


def missing_rows(df: pd.DataFrame, columns: list[str]) -> int:
    if not columns or any(column not in df.columns for column in columns):
        return 0
    return int(df[columns].isna().any(axis=1).sum())


def duplicate_rows(df: pd.DataFrame, columns: list[str]) -> int:
    if not columns or any(column not in df.columns for column in columns):
        return 0
    return int(df.duplicated(columns, keep=False).sum())


def key_diagnostics(df: pd.DataFrame, columns: list[str]) -> dict[str, Any]:
    missing = missing_rows(df, columns)
    duplicates = duplicate_rows(df, columns)
    missing_columns = [column for column in columns if column not in df.columns]
    return {
        "columns": columns,
        "missing_columns": missing_columns,
        "missing_rows": missing,
        "duplicate_rows": duplicates,
        "unique": not missing_columns and missing == 0 and duplicates == 0,
    }


def critical_variable_diagnostics(df: pd.DataFrame, variables: list[str]) -> dict[str, Any]:
    missing_rates: dict[str, float | None] = {}
    existing = [var for var in variables if var in df.columns]
    for var in variables:
        missing_rates[var] = None if var not in df.columns else float(df[var].isna().mean())
    complete_case_rows = int(df[existing].notna().all(axis=1).sum()) if existing else 0
    complete_case_rate = float(complete_case_rows / len(df)) if len(df) else 0.0
    return {
        "variables": variables,
        "missing_rates": missing_rates,
        "complete_case_rows": complete_case_rows,
        "complete_case_rate": complete_case_rate,
    }


def dataframe_profile(name: str, df: pd.DataFrame, key: list[str] | None = None) -> dict[str, Any]:
    missing_rates = {column: float(df[column].isna().mean()) for column in df.columns}
    profile: dict[str, Any] = {
        "name": name,
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "column_names": list(df.columns),
        "dtypes": {column: str(dtype) for column, dtype in df.dtypes.items()},
        "missing_rates": missing_rates,
    }
    if key:
        profile["key"] = key_diagnostics(df, key)
    return profile
