"""Shared hard-gate checks for starlane-data-cleaner diagnostics."""

from __future__ import annotations

from typing import Any


ROW_EXPANSION_TOLERANCE = 1e-6


def basic_hard_gate_failures(
    *,
    validation: dict[str, Any],
    required_missing: list[str],
    key_diag: dict[str, Any],
    critical_diag: dict[str, Any],
) -> list[str]:
    failures: list[str] = []
    if required_missing:
        failures.append("required_columns_missing")
    if key_diag["missing_columns"]:
        failures.append("target_key_columns_missing")
    if key_diag["missing_rows"]:
        failures.append("target_key_missing")
    if validation.get("require_unique_target_key", True) and not key_diag["unique"]:
        failures.append("duplicate_target_key")
    max_missing = validation.get("max_critical_missing_rate")
    if max_missing is not None:
        for rate in critical_diag["missing_rates"].values():
            if rate is not None and rate > max_missing:
                failures.append("critical_missing_rate_above_threshold")
                break
    return failures
