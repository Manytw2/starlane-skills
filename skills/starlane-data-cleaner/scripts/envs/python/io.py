"""Data IO helpers for the Python cleaner env."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def read_data(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    if suffix == ".dta":
        return pd.read_stata(path)
    raise ValueError(f"Unsupported input format: {path.suffix}")


def write_data(df: pd.DataFrame, path: Path, fmt: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "csv":
        df.to_csv(path, index=False)
        return
    if fmt == "dta":
        df.to_stata(path, write_index=False, version=118)
        return
    raise ValueError(f"Unsupported output format: {fmt}")
