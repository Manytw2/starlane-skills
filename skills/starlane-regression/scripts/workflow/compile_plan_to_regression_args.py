"""Compile a guided Starlane analysis plan to regression argument order."""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any


REGRESSION_ARG_NAMES = [
    "input_dta",
    "y",
    "x",
    "cv",
    "cv_fixed",
    "cv_min_count",
    "panelvar",
    "timevar",
    "meds",
    "mods",
    "heterogeneity_discrete",
    "heterogeneity_discrete_values",
    "rob_vars",
    "y_ln",
    "x_ln",
    "rob_year_range",
    "iv",
    "coef_direction",
]


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


def join_space(value: Any) -> str:
    return " ".join(list_value(value))


def join_pipe(value: Any) -> str:
    return "|".join(list_value(value))


def bool_regression_arg(value: Any, default: bool = False) -> str:
    if value is None:
        value = default
    return "1" if bool(value) else "0"


def get_dict(parent: dict[str, Any], key: str) -> dict[str, Any]:
    value = parent.get(key, {})
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    return value


def compile_rob_vars(robustness: dict[str, Any]) -> tuple[str, str, str, str]:
    if not robustness.get("enabled", False):
        return "", "0", "0", ""

    parts: list[str] = []
    alt_y = join_space(robustness.get("alternative_outcomes", []))
    if alt_y:
        parts.append(f"alt_y:{alt_y}")
    alt_x = join_space(robustness.get("alternative_explanatory_vars", []))
    if alt_x:
        parts.append(f"alt_x:{alt_x}")
    lags = join_space(robustness.get("lag_explanatory_vars", []))
    if lags:
        parts.append(f"lag:{lags}")

    sample_window = robustness.get("sample_window")
    if isinstance(sample_window, dict) and sample_window.get("start") is not None and sample_window.get("end") is not None:
        rob_year_range = f"{sample_window['start']}:{sample_window['end']}"
    else:
        rob_year_range = ""

    return "|".join(parts), bool_regression_arg(robustness.get("log_y")), bool_regression_arg(robustness.get("log_x")), rob_year_range


def compile_heterogeneity_values(raw: Any) -> str:
    if not raw:
        return ""
    if not isinstance(raw, dict):
        raise ValueError("heterogeneity.selected_values must be an object")
    parts: list[str] = []
    for key, value in raw.items():
        values = [str(v) for v in list_value(value)]
        if values:
            parts.append(f"{key}:{';'.join(values)}")
    return "|".join(parts)


def compile_plan(plan: dict[str, Any]) -> list[str]:
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

    outcomes = join_space(baseline.get("outcomes", []))
    explanatory = join_space(baseline.get("explanatory_vars", []))
    cv = join_space(controls.get("search_pool", []))
    cv_fixed = join_space(controls.get("always_include", []))
    cv_min_count = str(controls.get("min_count", 0))
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

    meds = join_pipe(mechanism.get("variables", [])) if mechanism.get("enabled", False) else ""
    mods = join_pipe(moderation.get("variables", [])) if moderation.get("enabled", False) else ""
    heterogeneity_discrete = join_pipe(heterogeneity.get("discrete_groups", [])) if heterogeneity.get("enabled", False) else ""
    heterogeneity_values = compile_heterogeneity_values(heterogeneity.get("selected_values", {})) if heterogeneity.get("enabled", False) else ""
    rob_vars, y_ln, x_ln, rob_year_range = compile_rob_vars(robustness)
    iv_vars = join_space(iv.get("instruments", [])) if iv.get("enabled", False) else ""
    coef_direction = str(research.get("expected_direction") or "positive").strip().lower()
    if coef_direction not in ("positive", "negative"):
        raise ValueError("research.expected_direction must be positive or negative")

    return [
        input_path,
        outcomes,
        explanatory,
        cv,
        cv_fixed,
        cv_min_count,
        panelvar,
        timevar,
        meds,
        mods,
        heterogeneity_discrete,
        heterogeneity_values,
        rob_vars,
        y_ln,
        x_ln,
        rob_year_range,
        iv_vars,
        coef_direction,
    ]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compile Starlane analysis plan to regression args.")
    parser.add_argument("plan_path", help="Analysis plan JSON or minimal YAML path")
    parser.add_argument("--output", "-o", help="Output regression args JSON path. Defaults to stdout.")
    parser.add_argument("--mapping-output", help="Optional output path for name/value mapping JSON.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv or sys.argv[1:])
        plan = load_plan(Path(args.plan_path))
        values = compile_plan(plan)
        if len(values) != 18:
            raise ValueError(f"Compiler produced {len(values)} args, expected 18")

        text = json.dumps(values, ensure_ascii=False, indent=2)
        if args.output:
            out = Path(args.output)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text + "\n", encoding="utf-8")
            print(f"STARLANE_REGRESSION_ARGS_OUTPUT: {out}")
        else:
            print(text)

        if args.mapping_output:
            mapping = dict(zip(REGRESSION_ARG_NAMES, values, strict=True))
            mapping_out = Path(args.mapping_output)
            mapping_out.parent.mkdir(parents=True, exist_ok=True)
            mapping_out.write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"STARLANE_REGRESSION_MAPPING_OUTPUT: {mapping_out}")
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
