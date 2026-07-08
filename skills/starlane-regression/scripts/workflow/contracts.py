"""Current JSON contracts for starlane-regression workflow stages."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REGRESSION_ARG_NAMES = (
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
)

STRUCTURED_REGRESSION_ARG_FIELDS = (
    "input_dta",
    "outcomes",
    "explanatory_vars",
    "controls",
    "panel",
    "robustness",
    "mechanism",
    "moderation",
    "heterogeneity",
    "iv",
    "execution",
)
SELECTION_FIELDS = ("cv_idx", "vce_idx")
REQUIRED_NONEMPTY_REGRESSION_ARGS = ("input_dta", "y", "x", "cv", "panelvar", "timevar", "coef_direction")
ROB_KEYS = {"alt_y", "alt_x", "ln_y", "ln_x", "lag"}
BOOL_TEXT_VALUES = {"", "0", "1", "yes", "no", "true", "false", "是", "否"}


def _read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _check_exact_keys(data: dict[str, Any], expected: tuple[str, ...], label: str) -> None:
    missing = [name for name in expected if name not in data]
    unknown = [name for name in data if name not in expected]
    if missing:
        raise ValueError(f"Missing {label} field(s): {', '.join(missing)}")
    if unknown:
        raise ValueError(f"Unknown {label} field(s): {', '.join(unknown)}")


def _parse_nonnegative_int(raw: Any, label: str) -> int:
    text = str(raw).strip()
    try:
        value = int(text)
    except ValueError as exc:
        raise ValueError(f"Invalid {label}: expected non-negative integer, got {raw!r}") from exc
    if value < 0:
        raise ValueError(f"Invalid {label}: expected non-negative integer, got {raw!r}")
    return value


def _parse_positive_int(raw: str, label: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"Invalid {label}: expected positive integer, got {raw!r}") from exc
    if value < 1:
        raise ValueError(f"Invalid {label}: expected positive integer, got {raw!r}")
    return value


def _require_object(data: Any, label: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError(f"Invalid {label}: expected object")
    return data


def _string_list(data: Any, label: str, *, required: bool = False) -> list[str]:
    if not isinstance(data, list):
        raise ValueError(f"Invalid {label}: expected array")
    out = [str(value).strip() for value in data if str(value).strip()]
    if required and not out:
        raise ValueError(f"Invalid {label}: expected at least one value")
    return out


def _join_space(values: list[str]) -> str:
    return " ".join(values)


def _join_pipe(values: list[str]) -> str:
    return "|".join(values)


def _bool_arg(value: Any, label: str) -> str:
    if not isinstance(value, bool):
        raise ValueError(f"Invalid {label}: expected boolean")
    return "1" if value else "0"


def validate_rob_vars(raw: str) -> None:
    if not raw.strip():
        return
    for item in raw.split("|"):
        item = item.strip()
        if not item:
            continue
        if ":" not in item:
            raise ValueError(f"Invalid regression_args.rob_vars: expected key:value segment, got {item!r}")
        key, value = item.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key not in ROB_KEYS:
            raise ValueError(f"Invalid regression_args.rob_vars: unknown key {key!r}")
        if not value:
            raise ValueError(f"Invalid regression_args.rob_vars: empty value for {key!r}")
        if key == "lag":
            for period in value.split():
                _parse_positive_int(period, "regression_args.rob_vars lag period")


def validate_heterogeneity_discrete_values(raw: str) -> None:
    if not raw.strip():
        return
    for item in raw.split("|"):
        item = item.strip()
        if not item:
            continue
        if ":" not in item:
            raise ValueError(f"Invalid regression_args.heterogeneity_discrete_values: expected var:v1;v2 segment, got {item!r}")
        key, values = item.split(":", 1)
        if not key.strip():
            raise ValueError("Invalid regression_args.heterogeneity_discrete_values: empty variable name")
        cleaned_values = [value.strip() for value in values.split(";") if value.strip()]
        if not cleaned_values:
            raise ValueError(f"Invalid regression_args.heterogeneity_discrete_values: no values for {key.strip()!r}")


def _robustness_to_flat(data: Any) -> tuple[str, str, str, str]:
    robustness = _require_object(data, "regression_args.robustness")
    _check_exact_keys(
        robustness,
        ("alternative_outcomes", "alternative_explanatory_vars", "lag_periods", "log_y", "log_x", "sample_window"),
        "regression_args.robustness",
    )
    parts: list[str] = []
    alt_y = _join_space(_string_list(robustness["alternative_outcomes"], "regression_args.robustness.alternative_outcomes"))
    if alt_y:
        parts.append(f"alt_y:{alt_y}")
    alt_x = _join_space(_string_list(robustness["alternative_explanatory_vars"], "regression_args.robustness.alternative_explanatory_vars"))
    if alt_x:
        parts.append(f"alt_x:{alt_x}")
    lag_periods = [_parse_positive_int(str(value), "regression_args.robustness.lag_periods") for value in _string_list(robustness["lag_periods"], "regression_args.robustness.lag_periods")]
    if lag_periods:
        parts.append("lag:" + " ".join(str(value) for value in lag_periods))

    sample_window = robustness["sample_window"]
    if sample_window is None:
        rob_year_range = ""
    else:
        window = _require_object(sample_window, "regression_args.robustness.sample_window")
        _check_exact_keys(window, ("start", "end"), "regression_args.robustness.sample_window")
        rob_year_range = f"{window['start']}:{window['end']}"

    return "|".join(parts), _bool_arg(robustness["log_y"], "regression_args.robustness.log_y"), _bool_arg(robustness["log_x"], "regression_args.robustness.log_x"), rob_year_range


def _heterogeneity_values_to_flat(raw: Any) -> str:
    values = _require_object(raw, "regression_args.heterogeneity.selected_values")
    parts: list[str] = []
    for key, value in values.items():
        selected = _string_list(value, f"regression_args.heterogeneity.selected_values.{key}")
        if selected:
            parts.append(f"{key}:{';'.join(selected)}")
    return "|".join(parts)


def flatten_structured_regression_args(data: dict[str, Any]) -> dict[str, str]:
    _check_exact_keys(data, STRUCTURED_REGRESSION_ARG_FIELDS, "regression_args")

    controls = _require_object(data["controls"], "regression_args.controls")
    _check_exact_keys(controls, ("search_pool", "always_include", "min_count"), "regression_args.controls")
    panel = _require_object(data["panel"], "regression_args.panel")
    _check_exact_keys(panel, ("entity", "time"), "regression_args.panel")
    mechanism = _require_object(data["mechanism"], "regression_args.mechanism")
    _check_exact_keys(mechanism, ("variables",), "regression_args.mechanism")
    moderation = _require_object(data["moderation"], "regression_args.moderation")
    _check_exact_keys(moderation, ("variables",), "regression_args.moderation")
    heterogeneity = _require_object(data["heterogeneity"], "regression_args.heterogeneity")
    _check_exact_keys(heterogeneity, ("discrete_groups", "selected_values"), "regression_args.heterogeneity")
    iv = _require_object(data["iv"], "regression_args.iv")
    _check_exact_keys(iv, ("instruments",), "regression_args.iv")
    execution = _require_object(data["execution"], "regression_args.execution")
    _check_exact_keys(execution, ("coef_direction",), "regression_args.execution")

    cv_min_count = _parse_nonnegative_int(controls["min_count"], "regression_args.controls.min_count")
    rob_vars, y_ln, x_ln, rob_year_range = _robustness_to_flat(data["robustness"])
    out = {
        "input_dta": str(data["input_dta"]).strip(),
        "y": _join_space(_string_list(data["outcomes"], "regression_args.outcomes", required=True)),
        "x": _join_space(_string_list(data["explanatory_vars"], "regression_args.explanatory_vars", required=True)),
        "cv": _join_space(_string_list(controls["search_pool"], "regression_args.controls.search_pool", required=True)),
        "cv_fixed": _join_space(_string_list(controls["always_include"], "regression_args.controls.always_include")),
        "cv_min_count": str(cv_min_count),
        "panelvar": str(panel["entity"]).strip(),
        "timevar": str(panel["time"]).strip(),
        "meds": _join_pipe(_string_list(mechanism["variables"], "regression_args.mechanism.variables")),
        "mods": _join_pipe(_string_list(moderation["variables"], "regression_args.moderation.variables")),
        "heterogeneity_discrete": _join_pipe(_string_list(heterogeneity["discrete_groups"], "regression_args.heterogeneity.discrete_groups")),
        "heterogeneity_discrete_values": _heterogeneity_values_to_flat(heterogeneity["selected_values"]),
        "rob_vars": rob_vars,
        "y_ln": y_ln,
        "x_ln": x_ln,
        "rob_year_range": rob_year_range,
        "iv": _join_space(_string_list(iv["instruments"], "regression_args.iv.instruments")),
        "coef_direction": str(execution["coef_direction"]).strip(),
    }
    return validate_internal_flat_regression_args(out)


def validate_internal_flat_regression_args(data: dict[str, str]) -> dict[str, str]:
    _check_exact_keys(data, REGRESSION_ARG_NAMES, "regression_args")

    out = {name: str(data[name]) for name in REGRESSION_ARG_NAMES}
    for name in REQUIRED_NONEMPTY_REGRESSION_ARGS:
        if not out[name].strip():
            raise ValueError(f"Invalid regression_args.{name}: value is required")
    _parse_nonnegative_int(out["cv_min_count"], "regression_args.cv_min_count")

    coef_direction = out["coef_direction"].strip().lower()
    if coef_direction not in {"positive", "negative"}:
        raise ValueError(f"Invalid regression_args.coef_direction: expected 'positive' or 'negative', got {out['coef_direction']!r}")
    out["coef_direction"] = coef_direction

    for name in ("y_ln", "x_ln"):
        value = out[name].strip().lower()
        if value not in BOOL_TEXT_VALUES:
            raise ValueError(f"Invalid regression_args.{name}: unsupported boolean value {out[name]!r}")

    validate_rob_vars(out["rob_vars"])
    validate_heterogeneity_discrete_values(out["heterogeneity_discrete_values"])
    return out


def validate_regression_args(data: Any) -> dict[str, str]:
    if isinstance(data, list):
        raise ValueError("Invalid regression_args: expected structured JSON object; arrays are not supported")
    if not isinstance(data, dict):
        raise ValueError("Invalid regression_args: expected structured JSON object")
    return flatten_structured_regression_args(data)


def load_regression_args_json(path: str | Path) -> dict[str, str]:
    try:
        return validate_regression_args(_read_json(path))
    except ValueError as exc:
        raise ValueError(f"{exc} in {path}") from exc


def validate_selection(data: Any) -> dict[str, int]:
    if not isinstance(data, dict):
        raise ValueError("Invalid selected_candidate: expected JSON object")
    _check_exact_keys(data, SELECTION_FIELDS, "selected_candidate")
    cv_idx = _parse_nonnegative_int(data["cv_idx"], "selected_candidate.cv_idx")
    vce_idx = _parse_nonnegative_int(data["vce_idx"], "selected_candidate.vce_idx")
    if vce_idx > 3:
        raise ValueError(f"Invalid selected_candidate.vce_idx: expected 0..3, got {data['vce_idx']!r}")
    return {"cv_idx": cv_idx, "vce_idx": vce_idx}


def load_selection_json(path: str | Path) -> dict[str, int]:
    try:
        return validate_selection(_read_json(path))
    except ValueError as exc:
        raise ValueError(f"{exc} in {path}") from exc
