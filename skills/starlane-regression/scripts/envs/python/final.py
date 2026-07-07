"""Python final-stage env for a selected Starlane regression row."""

from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt

from common import (
    RegressionArgs,
    apply_spec_condition,
    build_specs,
    compute_cv_subset,
    copy_source_to_dir,
    encode_panel_if_needed,
    ensure_columns,
    fail,
    format_coef,
    make_base_sample,
    prepare_regression_data,
    parse_cli_values,
    read_data,
    run_spec,
    spec_required_columns,
    split_words,
    stars_for_result,
    vce_suffix,
)


SECTION_TITLES = {
    "baseline_nocv": "Baseline regression: no controls",
    "baseline_cv": "Baseline regression: selected controls",
    "robustness_alt_x": "Robustness: alternative X",
    "robustness_alt_y": "Robustness: alternative Y",
    "robustness_ln_x": "Robustness: log X",
    "robustness_ln_y": "Robustness: log Y",
    "robustness_lag": "Robustness: lagged X",
    "robustness_year": "Robustness: sample window",
    "iv_stage1": "IV: first stage",
    "iv_stage2": "IV: second stage",
}


def section_title(section: str) -> str:
    if section in SECTION_TITLES:
        return SECTION_TITLES[section]
    if section.startswith("mediation_"):
        return f"Mediation: {section.removeprefix('mediation_')}"
    if section.startswith("moderation_"):
        return f"Moderation: {section.removeprefix('moderation_')}"
    if section.startswith("heterogeneity_discrete_"):
        return f"Heterogeneity: {section.removeprefix('heterogeneity_discrete_')}"
    return section.replace("_", " ").title()


def model_label(row: dict[str, str], idx: int) -> str:
    pieces = [f"({idx})"]
    if row["depvar"]:
        pieces.append(row["depvar"])
    if row["target"]:
        pieces.append(row["target"])
    if row["condition"]:
        pieces.append(row["condition"])
    return "\n".join(pieces)


def set_cell_text(cell, text: str, *, bold: bool = False, align: int | None = None) -> None:
    cell.text = ""
    paragraph = cell.paragraphs[0]
    if align is not None:
        paragraph.alignment = align
    run = paragraph.add_run(text)
    run.bold = bold
    run.font.name = "Times New Roman"
    run.font.size = Pt(9)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def add_regression_table(doc: Document, title: str, rows: list[dict[str, str]]) -> None:
    doc.add_heading(title, level=2)
    table = doc.add_table(rows=1, cols=len(rows) + 1)
    table.style = "Table Grid"
    set_cell_text(table.rows[0].cells[0], "Variable", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
    for idx, row in enumerate(rows, start=1):
        set_cell_text(table.rows[0].cells[idx], model_label(row, idx), bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)

    coef_row = table.add_row().cells
    set_cell_text(coef_row[0], "Coefficient")
    for idx, row in enumerate(rows, start=1):
        set_cell_text(coef_row[idx], row["coef_with_stars"], align=WD_ALIGN_PARAGRAPH.CENTER)

    se_row = table.add_row().cells
    set_cell_text(se_row[0], "Std. error")
    for idx, row in enumerate(rows, start=1):
        se = f"({row['se']})" if row["se"] else ""
        set_cell_text(se_row[idx], se, align=WD_ALIGN_PARAGRAPH.CENTER)

    n_row = table.add_row().cells
    set_cell_text(n_row[0], "Observations")
    for idx, row in enumerate(rows, start=1):
        set_cell_text(n_row[idx], row["nobs"], align=WD_ALIGN_PARAGRAPH.CENTER)

    r2_row = table.add_row().cells
    set_cell_text(r2_row[0], "R-squared")
    for idx, row in enumerate(rows, start=1):
        set_cell_text(r2_row[idx], row["r2"], align=WD_ALIGN_PARAGRAPH.CENTER)

    entity_fe_row = table.add_row().cells
    set_cell_text(entity_fe_row[0], "Entity FE")
    for idx in range(1, len(rows) + 1):
        set_cell_text(entity_fe_row[idx], "Yes", align=WD_ALIGN_PARAGRAPH.CENTER)

    time_fe_row = table.add_row().cells
    set_cell_text(time_fe_row[0], "Time FE")
    for idx in range(1, len(rows) + 1):
        set_cell_text(time_fe_row[idx], "Yes", align=WD_ALIGN_PARAGRAPH.CENTER)

    note = doc.add_paragraph("Standard errors in parentheses; *** p<0.01, ** p<0.05, * p<0.1.")
    note.paragraph_format.space_after = Pt(8)
    for run in note.runs:
        run.font.name = "Times New Roman"
        run.font.size = Pt(9)


def write_docx(path: Path, rows: list[dict[str, str]], metadata: dict[str, str]) -> None:
    doc = Document()
    section = doc.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = section.page_height, section.page_width
    section.top_margin = Inches(0.6)
    section.bottom_margin = Inches(0.6)
    section.left_margin = Inches(0.6)
    section.right_margin = Inches(0.6)

    styles = doc.styles
    styles["Normal"].font.name = "Times New Roman"
    styles["Normal"].font.size = Pt(10)

    doc.add_heading("Starlane Python Regression Results", level=1)
    for key, value in metadata.items():
        doc.add_paragraph(f"{key}: {value}")

    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(row["section"], []).append(row)
    for section_name, section_rows in grouped.items():
        add_regression_table(doc, section_title(section_name), section_rows)

    doc.save(path)


def run_final(values: list[str], output_arg: str | None = None, source_path: str | None = None) -> dict[str, str]:
    if len(values) < 20:
        raise ValueError("Expected 18 summary args + cv_idx + vce_idx + optional result_dir")
    args = RegressionArgs.from_list(values)
    cv_idx = int(values[18])
    vce_idx = int(values[19])
    result_dir = Path(values[20]) if len(values) > 20 and values[20].strip() else Path(os.environ.get("STARLANE_EXPORT", ".starlane"))
    if output_arg:
        result_dir = Path(output_arg)
    result_dir.mkdir(parents=True, exist_ok=True)

    y_vars = split_words(args.y)
    x_vars = split_words(args.x)
    cv_all = split_words(args.cv)
    cv_fixed = split_words(args.cv_fixed)
    cv_min_count = int(args.cv_min_count.strip() or "0")
    coef_direction = (args.coef_direction.strip().lower() or "positive")
    cv_subset = compute_cv_subset(cv_all, cv_fixed, cv_min_count, cv_idx)

    optional_originals = split_words(args.meds) + split_words(args.mods) + split_words(args.iv)
    df = read_data(args.input_dta)
    ensure_columns(df, [*y_vars, *x_vars, *cv_all, args.panelvar, args.timevar, *optional_originals])
    df = prepare_regression_data(df, args)
    df, panelvar = encode_panel_if_needed(df, args.panelvar)
    timevar = args.timevar
    specs = build_specs(args, cv_subset)
    ensure_columns(df, [panelvar, timevar, *spec_required_columns(specs)])
    base_sample = make_base_sample(df, [panelvar, timevar, *spec_required_columns(specs)])

    rows: list[dict[str, str]] = []
    for spec in specs:
        spec_sample = apply_spec_condition(df, base_sample, spec)
        result = run_spec(df, spec, panelvar, timevar, vce_idx, spec_sample)
        stars = stars_for_result(result, coef_direction)
        rows.append(
            {
                "column": spec.column,
                "section": spec.section,
                "depvar": spec.depvar,
                "target": spec.target_var,
                "controls": " ".join(spec.controls),
                "condition": f"{spec.condition_var}={spec.condition_value}" if spec.condition_var else "",
                "coef": "" if result is None else f"{result.coef:.10g}",
                "se": "" if result is None else f"{result.se:.10g}",
                "p_value": "" if result is None else f"{result.p_value:.10g}",
                "stars": "*" * stars,
                "coef_with_stars": format_coef(result, stars),
                "nobs": "" if result is None else str(result.nobs),
                "r2": "" if result is None else f"{result.r2:.10g}",
            }
        )

    csv_path = result_dir / "final_result.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = ["column", "section", "depvar", "target", "controls", "condition", "coef", "se", "p_value", "stars", "coef_with_stars", "nobs", "r2"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    md_path = result_dir / "final_result.md"
    metadata = {
        "input": args.input_dta,
        "cv_idx": str(cv_idx),
        "vce_idx": str(vce_idx),
        "vce_suffix": vce_suffix(vce_idx, panelvar, timevar),
        "cv_selected": " ".join(cv_subset),
    }
    md_lines = [
        "# Starlane Python Final Result",
        "",
        *[f"- {key}: `{value}`" for key, value in metadata.items()],
        "",
        "| section | depvar | target | controls | condition | coef | se | p | nobs | r2 |",
        "| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        md_lines.append(
            f"| {row['section']} | {row['depvar']} | {row['target']} | {row['controls']} | {row['condition']} | {row['coef_with_stars']} | {row['se']} | {row['p_value']} | {row['nobs']} | {row['r2']} |"
        )
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    docx_path = result_dir / "final_result.docx"
    write_docx(docx_path, rows, metadata)

    run_note = result_dir / "python_env_run_note.md"
    run_note.write_text(
        "\n".join(
            [
                "# Python Env Run Note",
                "",
                "This Python env implements the Starlane summary/final workflow contract across the same section families as the Stata env.",
                "",
                "It uses an internal numpy OLS implementation with absorbed panel and time fixed effects.",
                "Numerical equivalence with Stata reghdfe is not guaranteed until cross-env tests are added.",
                "",
                "Raw args:",
                "",
                "```json",
                json.dumps([*args.base_list(), str(cv_idx), str(vce_idx), str(result_dir)], ensure_ascii=False, indent=2),
                "```",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    source_copy = copy_source_to_dir(Path(source_path or __file__), result_dir)
    return {
        "csv": str(csv_path),
        "markdown": str(md_path),
        "docx": str(docx_path),
        "source": str(source_copy),
        "run_note": str(run_note),
    }


def main() -> int:
    try:
        values, output_arg = parse_cli_values(sys.argv)
        outputs = run_final(values, output_arg=output_arg)
        print(f"STARLANE_FINAL_OUTPUT: {outputs['docx']}")
        print(f"STARLANE_SOURCE_ARTIFACT: {outputs['source']}")
        return 0
    except Exception as e:
        return fail(str(e))


if __name__ == "__main__":
    sys.exit(main())
