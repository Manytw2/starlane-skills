"""Shared helpers for the Python regression env."""

from __future__ import annotations

import csv
import math
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import pyfixest as pf

WORKFLOW_SCRIPTS = Path(__file__).resolve().parents[2] / "workflow"
if str(WORKFLOW_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(WORKFLOW_SCRIPTS))

from contracts import REGRESSION_ARG_NAMES, load_regression_args_json, load_selection_json  # noqa: E402


@dataclass(frozen=True)
class RegressionArgs:
    input_dta: str
    y: str
    x: str
    cv: str
    cv_fixed: str
    cv_min_count: str
    panelvar: str
    timevar: str
    meds: str
    mods: str
    heterogeneity_discrete: str
    heterogeneity_discrete_values: str
    rob_vars: str
    y_ln: str
    x_ln: str
    rob_year_range: str
    iv: str
    coef_direction: str

    @classmethod
    def from_mapping(cls, values: dict[str, object]) -> "RegressionArgs":
        missing = [name for name in REGRESSION_ARG_NAMES if name not in values]
        if missing:
            raise ValueError(f"Missing regression arg field(s): {', '.join(missing)}")
        return cls(**{name: str(values[name]) for name in REGRESSION_ARG_NAMES})

    def as_mapping(self) -> dict[str, str]:
        return {name: getattr(self, name) for name in REGRESSION_ARG_NAMES}


@dataclass(frozen=True)
class RegressionResult:
    coef: float
    se: float
    nobs: int
    r2: float
    coefficients: dict[str, float]
    standard_errors: dict[str, float]
    p_values: dict[str, float]
    target_name: str

    @property
    def p_value(self) -> float:
        value = self.p_values.get(self.target_name)
        return value if value is not None else math.nan


@dataclass(frozen=True)
class RegressionSpec:
    column: str
    section: str
    depvar: str
    target_var: str
    controls: tuple[str, ...]
    condition_var: str = ""
    condition_value: str = ""
    score: bool = True
    instrument: str = ""


@dataclass(frozen=True)
class RegressionAttempt:
    result: RegressionResult | None
    reason: str = ""
    detail: dict[str, object] | None = None


def reject_positional_args(argv: list[str]) -> None:
    if len(argv) > 1 and not argv[1].startswith("-"):
        raise ValueError("Positional regression args are no longer supported. Use --args-json PATH.")


def split_words(raw: str) -> list[str]:
    return [v for v in raw.replace("|", " ").split() if v]


def parse_bool_default_yes(raw: str) -> bool:
    return raw.strip().lower() in ("", "1", "yes", "true", "是")


def parse_rob_vars(raw: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in raw.split("|"):
        item = item.strip()
        if not item or ":" not in item:
            continue
        key, value = item.split(":", 1)
        out[key.strip()] = value.strip()
    return out


def parse_discrete_values(raw: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    if not raw.strip():
        return out
    for item in raw.split("|"):
        if ":" not in item:
            continue
        key, values = item.split(":", 1)
        cleaned = [v.strip() for v in values.split(";") if v.strip()]
        if key.strip() and cleaned:
            out[key.strip()] = cleaned
    return out


def compute_cv_subsets(cv_all: list[str], cv_fixed: list[str], cv_min_count: int) -> list[list[str]]:
    optional = [v for v in cv_all if v not in cv_fixed]
    min_extra = max(0, cv_min_count - len(cv_fixed))
    out: list[list[str]] = []
    for mask in range(2 ** len(optional)):
        chosen = [optional[i] for i in range(len(optional)) if (mask >> i) & 1]
        if len(chosen) < min_extra:
            continue
        out.append([*cv_fixed, *chosen])
    return out


def compute_cv_subset(cv_all: list[str], cv_fixed: list[str], cv_min_count: int, cv_idx: int) -> list[str]:
    subsets = compute_cv_subsets(cv_all, cv_fixed, cv_min_count)
    if cv_idx < 0 or cv_idx >= len(subsets):
        raise ValueError("cv_idx out of range for given cv/cv_fixed/cv_min_count")
    return subsets[cv_idx]


def vce_suffix(vce_idx: int, panelvar: str, timevar: str) -> str:
    if vce_idx == 0:
        return "ols"
    if vce_idx == 1:
        return "robust"
    if vce_idx == 2:
        return f"cluster_{panelvar}"
    if vce_idx == 3:
        return f"cluster_{panelvar}_{timevar}"
    raise ValueError("vce_idx must be 0-3")


def read_data(path: str) -> pd.DataFrame:
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".dta":
        return pd.read_stata(p)
    if suffix == ".csv":
        return pd.read_csv(p)
    if suffix in (".xls", ".xlsx"):
        return pd.read_excel(p)
    raise ValueError(f"Unsupported input format: {path}")


def ensure_columns(df: pd.DataFrame, columns: Iterable[str]) -> None:
    missing = [c for c in columns if c and c not in df.columns]
    if missing:
        raise ValueError(f"Missing variable(s): {', '.join(missing)}")


def prepare_regression_data(df: pd.DataFrame, args: RegressionArgs) -> pd.DataFrame:
    out = df.copy()
    rob = parse_rob_vars(args.rob_vars)
    y_vars = split_words(args.y)
    x_vars = split_words(args.x)
    if parse_bool_default_yes(args.x_ln):
        for x in x_vars:
            name = f"{x}_rob_ln_{x}"
            if name not in out.columns:
                values = pd.to_numeric(out[x], errors="coerce")
                out[name] = np.where(values > 0, np.log(values), np.nan)
    for x in split_words(rob.get("ln_x", "")):
        name = f"{x}_rob_ln_{x}"
        if name not in out.columns and x in out.columns:
            values = pd.to_numeric(out[x], errors="coerce")
            out[name] = np.where(values > 0, np.log(values), np.nan)
    if parse_bool_default_yes(args.y_ln):
        for y in y_vars:
            name = f"{y}_rob_ln_{y}"
            if name not in out.columns:
                values = pd.to_numeric(out[y], errors="coerce")
                out[name] = np.where(values > 0, np.log(values), np.nan)
    for y in split_words(rob.get("ln_y", "")):
        name = f"{y}_rob_ln_{y}"
        if name not in out.columns and y in out.columns:
            values = pd.to_numeric(out[y], errors="coerce")
            out[name] = np.where(values > 0, np.log(values), np.nan)
    if rob.get("lag"):
        out = out.sort_values([args.panelvar, args.timevar]).copy()
        for period in split_words(rob["lag"]):
            try:
                p = int(period)
            except ValueError:
                continue
            for x in x_vars:
                out[f"l{p}_{x}"] = out.groupby(args.panelvar, sort=False)[x].shift(p)
    for x in x_vars:
        values = pd.to_numeric(out[x], errors="coerce")
        std = values.std()
        out[f"std_x_{x}"] = (values - values.mean()) / std if std and np.isfinite(std) else np.nan
    for mod in split_words(args.mods):
        if mod in out.columns:
            values = pd.to_numeric(out[mod], errors="coerce")
            std = values.std()
            out[f"std_mod_{mod}"] = (values - values.mean()) / std if std and np.isfinite(std) else np.nan
            for x in x_vars:
                out[f"interaction_{x}_{mod}"] = out[f"std_x_{x}"] * out[f"std_mod_{mod}"]
    return out


def build_specs(args: RegressionArgs, cv_subset: list[str]) -> list[RegressionSpec]:
    y_vars = split_words(args.y)
    x_vars = split_words(args.x)
    rob = parse_rob_vars(args.rob_vars)
    specs: list[RegressionSpec] = []
    for y in y_vars:
        for x in x_vars:
            specs.append(RegressionSpec(f"baseline__{y}__{x}__nocv", "baseline_nocv", y, x, ()))
    for y in y_vars:
        for x in x_vars:
            specs.append(RegressionSpec(f"baseline__{y}__{x}__cv", "baseline_cv", y, x, tuple(cv_subset)))
    for alt_x in split_words(rob.get("alt_x", "")):
        for y in y_vars:
            specs.append(RegressionSpec(f"robustness_altx__{y}__{alt_x}", "robustness_alt_x", y, alt_x, tuple(cv_subset)))
    for alt_y in split_words(rob.get("alt_y", "")):
        for x in x_vars:
            specs.append(RegressionSpec(f"robustness_alty__{alt_y}__{x}", "robustness_alt_y", alt_y, x, tuple(cv_subset)))
    ln_x_targets = []
    if parse_bool_default_yes(args.x_ln):
        ln_x_targets.extend((x, f"{x}_rob_ln_{x}") for x in x_vars)
    ln_x_targets.extend((x, f"{x}_rob_ln_{x}") for x in split_words(rob.get("ln_x", "")))
    for original, target in ln_x_targets:
        for y in y_vars:
            specs.append(RegressionSpec(f"robustness_lnx__{y}__{original}", "robustness_ln_x", y, target, tuple(cv_subset)))
    ln_y_targets = []
    if parse_bool_default_yes(args.y_ln):
        ln_y_targets.extend((y, f"{y}_rob_ln_{y}") for y in y_vars)
    ln_y_targets.extend((y, f"{y}_rob_ln_{y}") for y in split_words(rob.get("ln_y", "")))
    for original, dep in ln_y_targets:
        for x in x_vars:
            specs.append(RegressionSpec(f"robustness_lny__{original}__{x}", "robustness_ln_y", dep, x, tuple(cv_subset)))
    for period in split_words(rob.get("lag", "")):
        for y in y_vars:
            for x in x_vars:
                specs.append(RegressionSpec(f"robustness_lag__{y}__{x}__l{period}", "robustness_lag", y, f"l{period}_{x}", tuple(cv_subset)))
    if args.rob_year_range.strip():
        for y in y_vars:
            for x in x_vars:
                specs.append(RegressionSpec(f"robustness_year__{y}__{x}", "robustness_year", y, x, tuple(cv_subset), args.timevar, args.rob_year_range.strip()))
    for y in y_vars:
        for x in x_vars:
            for iv in split_words(args.iv):
                specs.append(RegressionSpec(f"iv__{y}__{x}__{iv}__stage1", "iv_stage1", x, iv, tuple(cv_subset)))
                specs.append(RegressionSpec(f"iv__{y}__{x}__{iv}__stage2", "iv_stage2", y, x, tuple(cv_subset), instrument=iv))
    for med in split_words(args.meds)[:1]:
        for y in y_vars:
            for x in x_vars:
                specs.append(RegressionSpec(f"mediation__{med}__{y}__{x}", f"mediation_{med}", y, x, tuple(cv_subset)))
        for x in x_vars:
            specs.append(RegressionSpec(f"mediation__{med}__M__{x}", f"mediation_{med}", med, x, tuple(cv_subset)))
    for mod in split_words(args.mods):
        for y in y_vars:
            for x in x_vars:
                specs.append(RegressionSpec(f"moderation__{mod}__{y}__{x}", f"moderation_{mod}", y, f"interaction_{x}_{mod}", tuple([*cv_subset, f"std_x_{x}", f"std_mod_{mod}"])))
    discrete = parse_discrete_values(args.heterogeneity_discrete_values)
    for group_var in split_words(args.heterogeneity_discrete):
        for y in y_vars:
            for x in x_vars:
                for value in discrete.get(group_var, []):
                    specs.append(RegressionSpec(f"heterogeneity_group__{group_var}__{value}__{y}__{x}", f"heterogeneity_discrete_{group_var}", y, x, tuple(cv_subset), group_var, value))
    return specs


def spec_required_columns(specs: list[RegressionSpec]) -> list[str]:
    out: list[str] = []
    for spec in specs:
        out.extend([spec.depvar, spec.target_var, *spec.controls])
        if spec.condition_var:
            out.append(spec.condition_var)
    return [c for c in dict.fromkeys(out) if c]


def apply_spec_condition(df: pd.DataFrame, sample: pd.Series, spec: RegressionSpec) -> pd.Series:
    if not spec.condition_var:
        return sample
    raw = spec.condition_value
    series = df[spec.condition_var]
    if ":" in raw:
        left, right = [v.strip() for v in raw.split(":", 1)]
        try:
            lo = float(left)
            hi = float(right)
            numeric = pd.to_numeric(series, errors="coerce")
            return sample & (numeric >= lo) & (numeric <= hi)
        except ValueError:
            pass
    try:
        value: object = float(raw)
        return sample & (pd.to_numeric(series, errors="coerce") == value)
    except ValueError:
        return sample & (series.astype(str) == raw)


def pyfixest_vcov(vce_idx: int, panelvar: str, timevar: str) -> str | dict[str, str]:
    if vce_idx == 0:
        return "iid"
    if vce_idx == 1:
        return "hetero"
    if vce_idx == 2:
        return {"CRV1": panelvar}
    if vce_idx == 3:
        return {"CRV1": f"{panelvar} + {timevar}"}
    raise ValueError("vce_idx must be 0-3")


def _quote_name(name: str) -> str:
    escaped = name.replace("`", "\\`")
    return f"`{escaped}`"


def _formula_terms(names: list[str]) -> str:
    return " + ".join(_quote_name(name) for name in names) if names else "1"


def _coerce_numeric(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = frame.copy()
    for col in columns:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def _series_value(values: pd.Series, name: str) -> float:
    if name in values.index:
        return float(values.loc[name])
    text_name = str(name)
    for key, value in values.items():
        if str(key) == text_name:
            return float(value)
    return math.nan


def _extract_result(model: object, target_var: str, nobs: int) -> RegressionResult | None:
    coefs = model.coef()
    ses = model.se()
    p_values = model.pvalue()
    coef = _series_value(coefs, target_var)
    se = _series_value(ses, target_var)
    p_value = _series_value(p_values, target_var)
    if not math.isfinite(coef):
        return None
    coefficients = {str(key): float(value) for key, value in coefs.items() if math.isfinite(float(value))}
    standard_errors = {str(key): float(value) for key, value in ses.items() if math.isfinite(float(value))}
    p_value_map = {str(key): float(value) for key, value in p_values.items() if math.isfinite(float(value))}
    return RegressionResult(
        coef=coef,
        se=se,
        nobs=nobs,
        r2=math.nan,
        coefficients=coefficients,
        standard_errors=standard_errors,
        p_values=p_value_map or {target_var: p_value},
        target_name=target_var,
    )


def _model_data(
    df: pd.DataFrame,
    sample: pd.Series,
    columns: list[str],
    numeric_columns: list[str],
) -> pd.DataFrame:
    data = _coerce_numeric(df.loc[sample, columns].copy().reset_index(drop=True), numeric_columns)
    return data.replace([np.inf, -np.inf], np.nan).dropna()


def fit_pyfixest(
    *,
    data: pd.DataFrame,
    formula: str,
    target_var: str,
    variance_check_columns: list[str],
    panelvar: str,
    timevar: str,
    vce_idx: int,
) -> RegressionAttempt:
    if len(data) < 30:
        return RegressionAttempt(None, "sample_below_min_n", {"nobs": int(len(data))})
    zero_variance = [col for col in variance_check_columns if data[col].std() == 0]
    if zero_variance:
        return RegressionAttempt(None, "zero_variance_regressor", {"columns": zero_variance, "nobs": int(len(data))})
    try:
        model = pf.feols(fml=formula, data=data, vcov=pyfixest_vcov(vce_idx, panelvar, timevar))
        result = _extract_result(model, target_var, len(data))
    except np.linalg.LinAlgError as exc:
        return RegressionAttempt(None, "linear_algebra_failed", {"message": str(exc), "nobs": int(len(data))})
    except Exception as exc:
        return RegressionAttempt(None, "pyfixest_failed", {"message": str(exc), "nobs": int(len(data))})
    if result is None:
        return RegressionAttempt(None, "non_finite_values", {"nobs": int(len(data))})
    return RegressionAttempt(result)


def run_spec(
    df: pd.DataFrame,
    spec: RegressionSpec,
    panelvar: str,
    timevar: str,
    vce_idx: int,
    sample: pd.Series,
) -> RegressionResult | None:
    return run_spec_attempt(df, spec, panelvar, timevar, vce_idx, sample).result


def run_spec_attempt(
    df: pd.DataFrame,
    spec: RegressionSpec,
    panelvar: str,
    timevar: str,
    vce_idx: int,
    sample: pd.Series,
) -> RegressionAttempt:
    if spec.section == "iv_stage2" and spec.instrument:
        controls = list(spec.controls)
        columns = [spec.depvar, spec.target_var, spec.instrument, *controls, panelvar, timevar]
        data = _model_data(df, sample, columns, [spec.depvar, spec.target_var, spec.instrument, *controls])
        formula = f"{_quote_name(spec.depvar)} ~ {_formula_terms(controls)} | {_quote_name(panelvar)} + {_quote_name(timevar)} | {_quote_name(spec.target_var)} ~ {_quote_name(spec.instrument)}"
        return fit_pyfixest(
            data=data,
            formula=formula,
            target_var=spec.target_var,
            variance_check_columns=[spec.target_var, spec.instrument, *controls],
            panelvar=panelvar,
            timevar=timevar,
            vce_idx=vce_idx,
        )
    regressors = [spec.target_var, *spec.controls]
    columns = [spec.depvar, *regressors, panelvar, timevar]
    data = _model_data(df, sample, columns, [spec.depvar, *regressors])
    formula = f"{_quote_name(spec.depvar)} ~ {_formula_terms(list(regressors))} | {_quote_name(panelvar)} + {_quote_name(timevar)}"
    return fit_pyfixest(
        data=data,
        formula=formula,
        target_var=spec.target_var,
        variance_check_columns=list(regressors),
        panelvar=panelvar,
        timevar=timevar,
        vce_idx=vce_idx,
    )


def encode_panel_if_needed(df: pd.DataFrame, panelvar: str) -> tuple[pd.DataFrame, str]:
    if pd.api.types.is_numeric_dtype(df[panelvar]):
        return df, panelvar
    out = df.copy()
    new_name = f"{panelvar}_gid"
    suffix = 0
    while new_name in out.columns:
        suffix += 1
        new_name = f"{panelvar}_g{suffix}"
    out[new_name] = pd.factorize(out[panelvar], sort=True)[0]
    return out, new_name


def make_base_sample(df: pd.DataFrame, vars_: list[str]) -> pd.Series:
    return df[vars_].notna().all(axis=1)


def stars_for_result(result: RegressionResult | None, coef_direction: str) -> int:
    if result is None or not math.isfinite(result.coef):
        return 0
    direction_ok = result.coef > 0 if coef_direction == "positive" else result.coef < 0
    if not direction_ok:
        return 0
    p = result.p_value
    if not math.isfinite(p):
        return 0
    if p < 0.01:
        return 3
    if p < 0.05:
        return 2
    if p < 0.1:
        return 1
    return 0


def format_coef(result: RegressionResult | None, stars: int) -> str:
    if result is None or not math.isfinite(result.coef):
        return ""
    return f"{result.coef:.6g}{'*' * stars}"


def write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def copy_source_to_dir(source: Path, result_dir: Path) -> Path:
    result_dir.mkdir(parents=True, exist_ok=True)
    target = result_dir / source.name
    if source.resolve() == target.resolve():
        return target
    shutil.copy2(source, target)
    return target


def fail(message: str) -> int:
    print(f"Error: {message}", file=sys.stderr)
    return 1
