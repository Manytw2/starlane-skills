"""JSON contracts for starlane-data-cleaner workflow stages."""

from __future__ import annotations

from pathlib import Path
from typing import Any


SUPPORTED_INPUT_FORMATS = {".csv", ".xlsx", ".xls", ".dta"}
SUPPORTED_OUTPUT_FORMATS = {"csv", "dta"}
SUPPORTED_MERGE_TYPES = {"1:1", "m:1", "1:m"}
SUPPORTED_UNMATCHED_POLICIES = {"keep_left_with_flag", "keep_matched", "keep_all_with_flag"}
SUPPORTED_CAST_TYPES = {"string", "int", "float", "date"}
SUPPORTED_DEDUP_METHODS = {"keep_first", "keep_last", "error"}


def require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    return value


def require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def resolve_path(path_value: str, cwd: Path) -> Path:
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        path = cwd / path
    return path


def validate_plan(plan: dict[str, Any]) -> None:
    require_mapping(plan, "plan")
    target = require_mapping(plan.get("target", {}), "target")
    if "key" in target:
        for key in require_list(target["key"], "target.key"):
            require_string(key, "target.key item")
    if "required_vars" in target:
        for var in require_list(target["required_vars"], "target.required_vars"):
            require_string(var, "target.required_vars item")
    if "critical_vars" in target:
        for var in require_list(target["critical_vars"], "target.critical_vars"):
            require_string(var, "target.critical_vars item")

    inputs = require_list(plan.get("inputs"), "inputs")
    input_names: set[str] = set()
    for idx, item in enumerate(inputs):
        input_item = require_mapping(item, f"inputs[{idx}]")
        name = require_string(input_item.get("name"), f"inputs[{idx}].name")
        require_string(input_item.get("path"), f"inputs[{idx}].path")
        if name in input_names:
            raise ValueError(f"duplicate input name: {name}")
        input_names.add(name)

    operations = require_list(plan.get("operations", []), "operations")
    for idx, operation in enumerate(operations):
        op = require_string(require_mapping(operation, f"operations[{idx}]").get("op"), f"operations[{idx}].op")
        if op == "merge":
            merge_type = require_string(operation.get("type"), f"operations[{idx}].type")
            if merge_type not in SUPPORTED_MERGE_TYPES:
                raise ValueError(f"unsupported merge type: {merge_type}")
            unmatched = operation.get("unmatched", "keep_left_with_flag")
            if unmatched not in SUPPORTED_UNMATCHED_POLICIES:
                raise ValueError(f"unsupported unmatched policy: {unmatched}")
        elif op == "cast":
            columns = require_mapping(operation.get("columns"), f"operations[{idx}].columns")
            for cast_type in columns.values():
                if cast_type not in SUPPORTED_CAST_TYPES:
                    raise ValueError(f"unsupported cast type: {cast_type}")
        elif op == "drop_duplicates":
            method = operation.get("method", "error")
            if method not in SUPPORTED_DEDUP_METHODS:
                raise ValueError(f"unsupported duplicate method: {method}")

    output = require_mapping(plan.get("output", {}), "output")
    formats = output.get("formats", ["csv"])
    for fmt in require_list(formats, "output.formats"):
        if fmt not in SUPPORTED_OUTPUT_FORMATS:
            raise ValueError(f"unsupported output format: {fmt}")
