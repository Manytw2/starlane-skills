"""Render canonical model-plan data into Stata env artifacts."""

from __future__ import annotations

from model_plan import ModelPlan


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
