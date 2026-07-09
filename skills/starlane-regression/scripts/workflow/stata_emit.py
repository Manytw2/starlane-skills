"""Render canonical model-plan data into Stata env artifacts."""

from __future__ import annotations

from pathlib import Path

from contracts import REGRESSION_ARG_NAMES
from model_plan import ModelPlan, RegressionArgsProxy, build_model_plan


STATA_ENV_SCRIPTS = Path(__file__).resolve().parents[1] / "envs" / "stata"

# Stata global macro names are limited to 31 chars; "starlane_" occupies 9.
# Register shorter aliases here when a field name would not fit.
STATA_ARG_GLOBAL_NAMES = {
    "heterogeneity_discrete_values": "het_disc_vals",
}


def quote_stata_arg(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def render_stata_model_plan_config(plan: ModelPlan) -> str:
    """Render plan metadata as Stata globals/locals.

    The current Stata summary env still owns execution loops. This generated
    block is the migration boundary for moving plan-derived rules out of
    summary.do without making Stata parse nested JSON.
    """

    lines = [
        "* Generated from Starlane ModelPlan. Do not edit by hand.",
        f"global starlane_plan_cv_subset_count {len(plan.cv_subsets)}",
        f"global starlane_plan_candidate_count {len(plan.candidates)}",
        f"global starlane_plan_summary_columns {quote_stata_arg(' '.join(plan.summary_columns))}",
    ]
    for subset in plan.cv_subsets:
        lines.append(f"global starlane_plan_cv_sub_{subset.cv_idx} {quote_stata_arg(' '.join(subset.controls))}")
    for choice in plan.vce_choices:
        lines.append(f"global starlane_plan_vce_suffix_{choice.vce_idx} {quote_stata_arg(choice.suffix)}")
        lines.append(f"global starlane_plan_vce_option_{choice.vce_idx} {quote_stata_arg(choice.stata_option)}")
    return "\n".join(lines) + "\n"


def render_stata_summary_config(
    args_values: dict[str, str],
    *,
    export_dir: Path,
    tmp_dir: Path,
    cv_idx_start: int | None = None,
    cv_idx_end: int | None = None,
    probe_only: bool = False,
    cache_dta: Path | None = None,
) -> str:
    """Render the full config .do consumed by scripts/envs/stata/summary.do."""

    lines = [
        f'global STARLANE_EXPORT "{export_dir.as_posix()}"',
        f'global STARLANE_TMP "{tmp_dir.as_posix()}"',
    ]
    if cache_dta is not None:
        lines.append(f'global STARLANE_CACHE_DTA "{cache_dta.as_posix()}"')
    for name in REGRESSION_ARG_NAMES:
        stata_name = STATA_ARG_GLOBAL_NAMES.get(name, name)
        lines.append(f"global starlane_{stata_name} {quote_stata_arg(args_values[name])}")
    lines.extend(
        [
            f'global starlane_cv_idx_start {quote_stata_arg("" if cv_idx_start is None else str(cv_idx_start))}',
            f'global starlane_cv_idx_end {quote_stata_arg("" if cv_idx_end is None else str(cv_idx_end))}',
            f'global starlane_probe_only {quote_stata_arg("1" if probe_only else "")}',
            'global starlane_csv_timestamp ""',
        ]
    )
    lines.append("")
    lines.append(render_stata_model_plan_config(build_model_plan(RegressionArgsProxy(args_values))).rstrip())
    return "\n".join(lines) + "\n"


def render_stata_summary_runner(config_path: Path, *, single_processor: bool = False) -> str:
    lines = []
    if single_processor:
        # Concurrent workers must not each grab all MP cores; SE/BE reject
        # `set processors`, hence capture.
        lines.append("capture set processors 1")
    lines.extend(
        [
            f'do "{config_path.as_posix()}"',
            f'do "{(STATA_ENV_SCRIPTS / "summary.do").as_posix()}"',
            "exit",
        ]
    )
    return "\n".join(lines) + "\n"
