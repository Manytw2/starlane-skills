"""Compile stage: analysis_plan -> regression args.

IN:  analysis_plan（JSON 或最小 YAML，研究层计划）
OUT: regression_args.json（执行层结构化契约，供 summary/final stage 使用）
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any


def load_plan(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    stripped = text.lstrip()
    if stripped.startswith("{"):
        data = json.loads(text)
    else:
        data = parse_minimal_yaml(text)
    if not isinstance(data, dict):
        raise ValueError("Analysis plan must be an object")
    return data


def parse_minimal_yaml(text: str) -> dict[str, Any]:
    """Parse the limited YAML subset used by Starlane plan examples.

    This avoids adding a new dependency while still accepting hand-written plans.
    For complex YAML, use JSON.
    """

    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        if ":" not in line:
            raise ValueError(f"Unsupported YAML line: {raw_line}")
        key, raw_value = line.split(":", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if not raw_value:
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = parse_scalar(raw_value)
    return root


def parse_scalar(raw: str) -> Any:
    if raw in ("null", "None", "~"):
        return None
    if raw in ("true", "True"):
        return True
    if raw in ("false", "False"):
        return False
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        try:
            value = ast.literal_eval(raw)
            if isinstance(value, list):
                return value
        except (ValueError, SyntaxError):
            pass
        return [item.strip().strip("'\"") for item in inner.split(",") if item.strip()]
    if raw.startswith("{") and raw.endswith("}"):
        return ast.literal_eval(raw)
    if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
        return ast.literal_eval(raw)
    try:
        return int(raw)
    except ValueError:
        return raw


def list_value(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if str(v)]
    if isinstance(value, str):
        return [v for v in value.replace("|", " ").split() if v]
    raise ValueError(f"Expected list or string, got {type(value).__name__}")


def get_dict(parent: dict[str, Any], key: str) -> dict[str, Any]:
    value = parent.get(key, {})
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    return value


def compile_plan_to_structured_args(plan: dict[str, Any]) -> dict[str, Any]:
    data = get_dict(plan, "data")
    research = get_dict(plan, "research")
    baseline = get_dict(plan, "baseline")
    controls = get_dict(baseline, "controls")
    fixed_effects = get_dict(baseline, "fixed_effects")
    robustness = get_dict(plan, "robustness")
    mechanism = get_dict(plan, "mechanism")
    moderation = get_dict(plan, "moderation")
    heterogeneity = get_dict(plan, "heterogeneity")
    iv = get_dict(plan, "iv")

    input_path = str(data.get("input_path", "")).strip()
    if not input_path:
        raise ValueError("data.input_path is required")
    outcomes = list_value(baseline.get("outcomes", []))
    explanatory = list_value(baseline.get("explanatory_vars", []))
    cv = list_value(controls.get("search_pool", []))
    panelvar = str(fixed_effects.get("entity") or get_dict(data, "panel").get("entity_var") or "").strip()
    timevar = str(fixed_effects.get("time") or get_dict(data, "panel").get("time_var") or "").strip()
    if not outcomes:
        raise ValueError("baseline.outcomes is required")
    if not explanatory:
        raise ValueError("baseline.explanatory_vars is required")
    if not cv:
        raise ValueError("baseline.controls.search_pool is required")
    if not panelvar:
        raise ValueError("baseline.fixed_effects.entity or data.panel.entity_var is required")
    if not timevar:
        raise ValueError("baseline.fixed_effects.time or data.panel.time_var is required")
    coef_direction = str(research.get("expected_direction") or "positive").strip().lower()
    if coef_direction not in ("positive", "negative"):
        raise ValueError("research.expected_direction must be positive or negative")

    sample_window = robustness.get("sample_window")
    if sample_window is not None and not isinstance(sample_window, dict):
        raise ValueError("robustness.sample_window must be an object or null")

    return {
        "data_path": input_path,
        "outcomes": outcomes,
        "explanatory_vars": explanatory,
        "controls": {
            "search_pool": cv,
            "always_include": list_value(controls.get("always_include", [])),
            "min_count": int(controls.get("min_count", 0)),
        },
        "panel": {
            "entity": panelvar,
            "time": timevar,
        },
        "robustness": {
            "alternative_outcomes": list_value(robustness.get("alternative_outcomes", [])) if robustness.get("enabled", False) else [],
            "alternative_explanatory_vars": list_value(robustness.get("alternative_explanatory_vars", [])) if robustness.get("enabled", False) else [],
            "lag_periods": [int(value) for value in list_value(robustness.get("lag_periods", []))] if robustness.get("enabled", False) else [],
            "ln_y": bool(robustness.get("ln_y", False)) if robustness.get("enabled", False) else False,
            "ln_x": bool(robustness.get("ln_x", False)) if robustness.get("enabled", False) else False,
            "sample_window": sample_window if robustness.get("enabled", False) else None,
        },
        "mechanism": {
            "variables": list_value(mechanism.get("variables", [])) if mechanism.get("enabled", False) else [],
        },
        "moderation": {
            "variables": list_value(moderation.get("variables", [])) if moderation.get("enabled", False) else [],
        },
        "heterogeneity": {
            "discrete_groups": list_value(heterogeneity.get("discrete_groups", [])) if heterogeneity.get("enabled", False) else [],
            "selected_values": heterogeneity.get("selected_values", {}) if heterogeneity.get("enabled", False) else {},
        },
        "iv": {
            "instruments": list_value(iv.get("instruments", [])) if iv.get("enabled", False) else [],
        },
        "execution": {
            "coef_direction": coef_direction,
        },
    }
