"""Canonical model-plan rules for Starlane regression stages.

This module answers "what should Starlane run?". Env-specific scripts answer
"how should this env run it?".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


SUMMARY_FIXED_COLUMNS = ("selection_id", "cv_idx", "vce_idx", "vce_suffix", "cv_selected", "score")


class RegressionArgsProxy:
    def __init__(self, values: dict[str, str]) -> None:
        self._values = values

    def __getattr__(self, name: str) -> str:
        try:
            return self._values[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


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


def stata_vce_option(vce_idx: int, panelvar: str, timevar: str) -> str:
    if vce_idx == 0:
        return "ols"
    if vce_idx == 1:
        return "robust"
    if vce_idx == 2:
        return f"cluster {panelvar}"
    if vce_idx == 3:
        return f"cluster {panelvar} {timevar}"
    raise ValueError("vce_idx must be 0-3")


@dataclass(frozen=True)
class ControlSubset:
    cv_idx: int
    controls: tuple[str, ...]


@dataclass(frozen=True)
class VceChoice:
    vce_idx: int
    suffix: str
    stata_option: str


@dataclass(frozen=True)
class Candidate:
    cv_idx: int
    vce_idx: int


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
class ModelPlan:
    cv_subsets: tuple[ControlSubset, ...]
    vce_choices: tuple[VceChoice, ...]
    full_specs: tuple[RegressionSpec, ...]
    summary_columns: tuple[str, ...]
    candidates: tuple[Candidate, ...]

    def cv_subset(self, cv_idx: int) -> ControlSubset:
        for subset in self.cv_subsets:
            if subset.cv_idx == cv_idx:
                return subset
        raise ValueError("cv_idx out of range for given cv/cv_fixed/cv_min_count")

    def vce_choice(self, vce_idx: int) -> VceChoice:
        for choice in self.vce_choices:
            if choice.vce_idx == vce_idx:
                return choice
        raise ValueError("vce_idx must be 0-3")

    def specs_for_cv_idx(self, args: Any, cv_idx: int) -> tuple[RegressionSpec, ...]:
        subset = self.cv_subset(cv_idx)
        return tuple(build_specs(args, list(subset.controls)))


def build_vce_choices(panelvar: str, timevar: str) -> list[VceChoice]:
    return [
        VceChoice(vce_idx=i, suffix=vce_suffix(i, panelvar, timevar), stata_option=stata_vce_option(i, panelvar, timevar))
        for i in range(4)
    ]


def build_model_plan(args: Any) -> ModelPlan:
    cv_all = split_words(str(getattr(args, "cv")))
    cv_fixed = split_words(str(getattr(args, "cv_fixed")))
    cv_min_count = int(str(getattr(args, "cv_min_count")).strip() or "0")
    panelvar = str(getattr(args, "panelvar"))
    timevar = str(getattr(args, "timevar"))

    cv_subsets = [
        ControlSubset(cv_idx=i, controls=tuple(controls))
        for i, controls in enumerate(compute_cv_subsets(cv_all, cv_fixed, cv_min_count))
    ]
    vce_choices = build_vce_choices(panelvar, timevar)
    full_specs = build_specs(args, cv_all)
    summary_columns = [*SUMMARY_FIXED_COLUMNS, *(spec.column for spec in full_specs)]
    candidates = [Candidate(subset.cv_idx, choice.vce_idx) for subset in cv_subsets for choice in vce_choices]
    return ModelPlan(
        cv_subsets=tuple(cv_subsets),
        vce_choices=tuple(vce_choices),
        full_specs=tuple(full_specs),
        summary_columns=tuple(summary_columns),
        candidates=tuple(candidates),
    )


def build_specs(args: object, cv_subset: list[str]) -> list[RegressionSpec]:
    y_vars = split_words(str(getattr(args, "y")))
    x_vars = split_words(str(getattr(args, "x")))
    rob = parse_rob_vars(str(getattr(args, "rob_vars")))
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
    if parse_bool_default_yes(str(getattr(args, "x_ln"))):
        ln_x_targets.extend((x, f"{x}_rob_ln_{x}") for x in x_vars)
    ln_x_targets.extend((x, f"{x}_rob_ln_{x}") for x in split_words(rob.get("ln_x", "")))
    for original, target in ln_x_targets:
        for y in y_vars:
            specs.append(RegressionSpec(f"robustness_lnx__{y}__{original}", "robustness_ln_x", y, target, tuple(cv_subset)))
    ln_y_targets = []
    if parse_bool_default_yes(str(getattr(args, "y_ln"))):
        ln_y_targets.extend((y, f"{y}_rob_ln_{y}") for y in y_vars)
    ln_y_targets.extend((y, f"{y}_rob_ln_{y}") for y in split_words(rob.get("ln_y", "")))
    for original, dep in ln_y_targets:
        for x in x_vars:
            specs.append(RegressionSpec(f"robustness_lny__{original}__{x}", "robustness_ln_y", dep, x, tuple(cv_subset)))
    for period in split_words(rob.get("lag", "")):
        for y in y_vars:
            for x in x_vars:
                specs.append(RegressionSpec(f"robustness_lag__{y}__{x}__l{period}", "robustness_lag", y, f"l{period}_{x}", tuple(cv_subset)))
    if str(getattr(args, "rob_year_range")).strip():
        for y in y_vars:
            for x in x_vars:
                specs.append(RegressionSpec(f"robustness_year__{y}__{x}", "robustness_year", y, x, tuple(cv_subset), str(getattr(args, "timevar")), str(getattr(args, "rob_year_range")).strip()))
    for y in y_vars:
        for x in x_vars:
            for iv in split_words(str(getattr(args, "iv"))):
                specs.append(RegressionSpec(f"iv__{y}__{x}__{iv}__stage1", "iv_stage1", x, iv, tuple(cv_subset)))
                specs.append(RegressionSpec(f"iv__{y}__{x}__{iv}__stage2", "iv_stage2", y, x, tuple(cv_subset), instrument=iv))
    for med in split_words(str(getattr(args, "meds")))[:1]:
        for y in y_vars:
            for x in x_vars:
                specs.append(RegressionSpec(f"mediation__{med}__{y}__{x}", f"mediation_{med}", y, x, tuple(cv_subset)))
        for x in x_vars:
            specs.append(RegressionSpec(f"mediation__{med}__M__{x}", f"mediation_{med}", med, x, tuple(cv_subset)))
    for mod in split_words(str(getattr(args, "mods"))):
        for y in y_vars:
            for x in x_vars:
                specs.append(RegressionSpec(f"moderation__{mod}__{y}__{x}", f"moderation_{mod}", y, f"interaction_{x}_{mod}", tuple([*cv_subset, f"std_x_{x}", f"std_mod_{mod}"])))
    discrete = parse_discrete_values(str(getattr(args, "heterogeneity_discrete_values")))
    for group_var in split_words(str(getattr(args, "heterogeneity_discrete"))):
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
