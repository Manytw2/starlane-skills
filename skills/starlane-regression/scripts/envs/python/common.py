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

    @property
    def t_stat(self) -> float:
        if not math.isfinite(self.se) or self.se <= 0:
            return math.nan
        return self.coef / self.se

    @property
    def p_value(self) -> float:
        t = abs(self.t_stat)
        if not math.isfinite(t):
            return math.nan
        # Normal approximation. Good enough for regression screening; document if used for publication.
        return math.erfc(t / math.sqrt(2.0))


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


def fit_fe_iv_2sls(
    df: pd.DataFrame,
    depvar: str,
    endogenous: str,
    instrument: str,
    controls: list[str],
    panelvar: str,
    timevar: str,
    vce_idx: int,
    sample: pd.Series,
) -> RegressionResult | None:
    needed = [depvar, endogenous, instrument, *controls, panelvar, timevar]
    data = df.loc[sample, needed].copy()
    for col in [depvar, endogenous, instrument, *controls]:
        data[col] = pd.to_numeric(data[col], errors="coerce")
    data = data.dropna()
    if len(data) < 30:
        return None
    columns = [depvar, endogenous, instrument, *controls]
    transformed = _within_transform(data, columns, panelvar, timevar)
    transformed = transformed.replace([np.inf, -np.inf], np.nan).dropna()
    if len(transformed) < 30:
        return None
    y = transformed[depvar].to_numpy(dtype=float)
    x_raw = transformed[[endogenous, *controls]].to_numpy(dtype=float)
    z_raw = transformed[[instrument, *controls]].to_numpy(dtype=float)
    if not np.isfinite(y).all() or not np.isfinite(x_raw).all() or not np.isfinite(z_raw).all():
        return None
    x_scale = x_raw.std(axis=0)
    z_scale = z_raw.std(axis=0)
    if np.any(~np.isfinite(x_scale)) or np.any(x_scale <= 0) or np.any(~np.isfinite(z_scale)) or np.any(z_scale <= 0):
        return None
    x = x_raw / x_scale
    z = z_raw / z_scale
    with np.errstate(all="ignore"):
        pzx = z @ (np.linalg.pinv(z.T @ z) @ z.T @ x)
        beta_scaled = np.linalg.lstsq(pzx, y, rcond=None)[0]
        resid = y - x @ beta_scaled
    if not np.isfinite(beta_scaled).all() or not np.isfinite(resid).all():
        return None
    cov = _cov_ols(x, resid) if vce_idx == 0 else _cov_hc1(x, resid)
    if not np.isfinite(cov).all():
        return None
    coef = float(beta_scaled[0] / x_scale[0])
    se = float(math.sqrt(max(cov[0, 0], 0.0)) / x_scale[0]) if cov.size else math.nan
    sst = float(((y - y.mean()) ** 2).sum())
    ssr = float((resid**2).sum())
    r2 = 1.0 - ssr / sst if sst > 0 else math.nan
    coefficients = {endogenous: coef}
    standard_errors = {endogenous: se}
    return RegressionResult(coef=coef, se=se, nobs=int(len(transformed)), r2=r2, coefficients=coefficients, standard_errors=standard_errors)


def run_spec(
    df: pd.DataFrame,
    spec: RegressionSpec,
    panelvar: str,
    timevar: str,
    vce_idx: int,
    sample: pd.Series,
) -> RegressionResult | None:
    if spec.section == "iv_stage2" and spec.instrument:
        return fit_fe_iv_2sls(
            df,
            spec.depvar,
            spec.target_var,
            spec.instrument,
            list(spec.controls),
            panelvar,
            timevar,
            vce_idx,
            sample,
        )
    return fit_fe_ols(df, spec.depvar, spec.target_var, list(spec.controls), panelvar, timevar, vce_idx, sample)


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


def _within_transform(frame: pd.DataFrame, columns: list[str], panelvar: str, timevar: str) -> pd.DataFrame:
    """Absorb two fixed effects by alternating demeaning.

    This avoids expanding thousands of dummy columns. It is a practical Python
    regression approximation to the fixed-effect absorption used by reghdfe.
    """
    out = frame[columns].astype(float).copy()
    for _ in range(8):
        before = out.to_numpy(copy=True)
        out -= out.groupby(frame[panelvar], sort=False).transform("mean")
        out -= out.groupby(frame[timevar], sort=False).transform("mean")
        out += out.mean()
        if np.nanmax(np.abs(out.to_numpy() - before)) < 1e-10:
            break
    return out


def _cov_ols(x: np.ndarray, resid: np.ndarray) -> np.ndarray:
    n, k = x.shape
    with np.errstate(all="ignore"):
        xtx_inv = np.linalg.pinv(x.T @ x)
        sigma2 = float(resid.T @ resid) / max(n - k, 1)
        return xtx_inv * sigma2


def _cov_hc1(x: np.ndarray, resid: np.ndarray) -> np.ndarray:
    n, k = x.shape
    with np.errstate(all="ignore"):
        xtx_inv = np.linalg.pinv(x.T @ x)
        meat = x.T @ ((resid[:, None] ** 2) * x)
        scale = n / max(n - k, 1)
        return scale * xtx_inv @ meat @ xtx_inv


def _cluster_meat(x: np.ndarray, resid: np.ndarray, groups: pd.Series) -> np.ndarray:
    meat = np.zeros((x.shape[1], x.shape[1]))
    with np.errstate(all="ignore"):
        for _, idx in groups.groupby(groups, sort=False).groups.items():
            loc = np.asarray(list(idx))
            xu = x[loc].T @ resid[loc]
            meat += np.outer(xu, xu)
    return meat


def _cov_cluster(x: np.ndarray, resid: np.ndarray, groups: pd.Series) -> np.ndarray:
    n, k = x.shape
    g = groups.nunique(dropna=True)
    with np.errstate(all="ignore"):
        xtx_inv = np.linalg.pinv(x.T @ x)
        scale = (g / max(g - 1, 1)) * ((n - 1) / max(n - k, 1))
        return scale * xtx_inv @ _cluster_meat(x, resid, groups.reset_index(drop=True)) @ xtx_inv


def _cov_cluster_two_way(x: np.ndarray, resid: np.ndarray, g1: pd.Series, g2: pd.Series) -> np.ndarray:
    cov1 = _cov_cluster(x, resid, g1)
    cov2 = _cov_cluster(x, resid, g2)
    joint = g1.astype(str).reset_index(drop=True) + "__" + g2.astype(str).reset_index(drop=True)
    cov12 = _cov_cluster(x, resid, joint)
    return cov1 + cov2 - cov12


def fit_fe_ols(
    df: pd.DataFrame,
    depvar: str,
    target_var: str,
    controls: list[str],
    panelvar: str,
    timevar: str,
    vce_idx: int,
    sample: pd.Series,
) -> RegressionResult | None:
    regressors = [target_var, *controls]
    needed = [depvar, *regressors, panelvar, timevar]
    data = df.loc[sample, needed].copy()
    for col in [depvar, *regressors]:
        data[col] = pd.to_numeric(data[col], errors="coerce")
    data = data.dropna()
    if len(data) < 30:
        return None
    transformed = _within_transform(data, [depvar, *regressors], panelvar, timevar)
    transformed = transformed.replace([np.inf, -np.inf], np.nan).dropna()
    if len(transformed) < 30:
        return None
    y = transformed[depvar].to_numpy(dtype=float)
    x_raw = transformed[regressors].to_numpy(dtype=float)
    if not np.isfinite(y).all() or not np.isfinite(x_raw).all():
        return None
    scale = x_raw.std(axis=0)
    if np.any(~np.isfinite(scale)) or np.any(scale <= 0):
        return None
    x = x_raw / scale
    names = regressors
    try:
        beta_scaled = np.linalg.lstsq(x, y, rcond=None)[0]
    except np.linalg.LinAlgError:
        return None
    if not np.isfinite(beta_scaled).all():
        return None
    with np.errstate(all="ignore"):
        resid = y - x @ beta_scaled
    if not np.isfinite(resid).all():
        return None
    if vce_idx == 0:
        cov = _cov_ols(x, resid)
    elif vce_idx == 1:
        cov = _cov_hc1(x, resid)
    elif vce_idx == 2:
        cov = _cov_cluster(x, resid, data[panelvar])
    else:
        cov = _cov_cluster_two_way(x, resid, data[panelvar], data[timevar])
    idx = names.index(target_var)
    if not np.isfinite(cov).all():
        return None
    unscaled_beta = beta_scaled / scale
    unscaled_se = np.sqrt(np.maximum(np.diag(cov), 0.0)) / scale if cov.size else np.full(len(names), math.nan)
    coef = float(unscaled_beta[idx])
    se = float(unscaled_se[idx])
    sst = float(((y - y.mean()) ** 2).sum())
    ssr = float((resid**2).sum())
    r2 = 1.0 - ssr / sst if sst > 0 else math.nan
    coefficients = {name: float(value) for name, value in zip(names, unscaled_beta)}
    standard_errors = {name: float(value) for name, value in zip(names, unscaled_se)}
    return RegressionResult(coef=coef, se=se, nobs=int(len(transformed)), r2=r2, coefficients=coefficients, standard_errors=standard_errors)


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
