"""Final stage (stata env): regression args + selection -> 可复现源码.

IN:  regression_args.json + selected_candidate.json（cv_idx / vce_idx）
OUT: 生成的 Stata .do 源码（运行后产出最终表格到 --result-dir）
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import unquote

WORKFLOW_SCRIPTS = Path(__file__).resolve().parents[2] / "workflow"
if str(WORKFLOW_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(WORKFLOW_SCRIPTS))

from contracts import REGRESSION_ARG_NAMES, load_regression_args_json, load_selection_json  # noqa: E402
from model_plan import RegressionArgsProxy, build_model_plan  # noqa: E402

# -----------------------------------------------------------------------------
# Block templates: each maps to regression_summary column structure.
# Placeholders: {y}, {x}, {m_idx}, {x_alt}, {y_alt}, {ln_x},
#               {ln_y}, {p}, {cond}, {med}, {mod}, {iv}
# -----------------------------------------------------------------------------

BLOCK_BASELINE_NOCV = "reghdfe {y} {x} if __base_sample, `reg_opts'\nest store m{m_idx}"
BLOCK_BASELINE_CV = "reghdfe {y} {x} `cv_selected' if __base_sample, `reg_opts'\nest store m{m_idx}"

BLOCK_ROB_ALT_X = "reghdfe {y} {x_alt} `cv_selected' if __base_sample, `reg_opts'\nest store m{m_idx}"
BLOCK_ROB_ALT_Y = "reghdfe {y_alt} {x} `cv_selected' if __base_sample, `reg_opts'\nest store m{m_idx}"
BLOCK_ROB_LN_X = "reghdfe {y} {ln_x} `cv_selected' if __base_sample, `reg_opts'\nest store m{m_idx}"
BLOCK_ROB_LN_Y = "reghdfe {ln_y} {x} `cv_selected' if __base_sample, `reg_opts'\nest store m{m_idx}"
BLOCK_ROB_LAG = "reghdfe {y} l{p}.{x} `cv_selected' if __base_sample, `reg_opts'\nest store m{m_idx}"
BLOCK_ROB_YEAR = "reghdfe {y} {x} `cv_selected' if __base_sample & {cond}, `reg_opts'\nest store m{m_idx}"

BLOCK_IV_STAGE1 = "reghdfe {x} {iv} `cv_selected' if __base_sample, `reg_opts'\nest store m{m_idx}"
BLOCK_IV_STAGE2 = "ivreghdfe {y} `cv_selected' ({x} = {iv}) if __base_sample, `reg_opts'\nest store m{m_idx}"

BLOCK_MED_TOTAL = "reghdfe {y} {x} `cv_selected' if __base_sample, `reg_opts'\nest store m{m_idx}"
BLOCK_MED_PATH_A = "reghdfe {med} {x} `cv_selected' if __base_sample, `reg_opts'\nest store m{m_idx}"

BLOCK_MOD_STD_X = "capture drop std_{x}\negen std_{x} = std({x})"
BLOCK_MOD_STD_MOD = "capture drop std_{mod}\negen std_{mod} = std({mod})"
BLOCK_MOD_REGRESS = "reghdfe {y} c.std_{x}##c.std_{mod} `cv_selected' if __base_sample, `reg_opts'\nest store m{m_idx}"
BLOCK_HET_DISCRETE = "reghdfe {y} {x} `cv_selected' if __base_sample & {cond}, `reg_opts'\nest store m{m_idx}"
BLOCK_FORCE_NUMERIC_HELPER = """* Force analysis vars to numeric in-place before shared-sample filtering.
capture program drop _force_numeric_var
program define _force_numeric_var
\targs varname

\tcapture confirm string variable `varname'
\tif _rc == 0 {
\t\ttempvar __numeric_probe
\t\tlocal can_destring 1

\t\tcapture gen double `__numeric_probe' = real(trim(`varname'))
\t\tif _rc != 0 {
\t\t\tlocal can_destring 0
\t\t}
\t\telse {
\t\t\tcapture count if trim(`varname') != "" & missing(`__numeric_probe')
\t\t\tif _rc != 0 | r(N) > 0 {
\t\t\t\tlocal can_destring 0
\t\t\t}
\t\t}

\t\tif `can_destring' == 1 {
\t\t\tcapture destring `varname', replace
\t\t}

\t\tcapture drop `__numeric_probe'
\t}
end"""

# Doc export templates (when export_doc=1)
# doc_common_nodepvar: use with mtitles(); reg2docx disallows mtitles() and depvar together
BLOCK_DOC_OPTS = '''local doc_star "star(* 0.1 ** 0.05 *** 0.01)"
local doc_b "b(%9.3f)"
local doc_se "se(%9.3f)"
local doc_scalar "scalars(N(%9.0fc) r2_a(%9.3f))"
local doc_fe `"addfe("Entity FE = Yes" "Time FE = Yes")"'
local doc_font "font(Times New Roman, 11)"
local doc_common "`doc_star' `doc_b' `doc_se' `doc_scalar' `doc_fe' depvar `doc_font'"
local doc_common_nodepvar "`doc_star' `doc_b' `doc_se' `doc_scalar' `doc_fe' `doc_font'"'''
BLOCK_REG2DOCX_REPLACE = 'reg2docx {models} using "`docxout\'", replace `doc_common\' title("Table {table_num}: {title}") note("Standard errors in parentheses; *** p<0.01, ** p<0.05, * p<0.1")'
BLOCK_REG2DOCX_APPEND = 'reg2docx {models} using "`docxout\'", append `doc_common\' title("Table {table_num}: {title}") note("Standard errors in parentheses; *** p<0.01, ** p<0.05, * p<0.1")'


def parse_rob_vars(rob_raw: str) -> dict[str, str]:
    """Parse rob_vars 'type:value|type:value' into dict."""
    out: dict[str, str] = {}
    if not rob_raw or not rob_raw.strip():
        return out
    for item in rob_raw.strip().split("|"):
        item = item.strip()
        if ":" in item:
            colon = item.index(":")
            t = item[:colon].strip()
            v = item[colon + 1 :].strip()
            if t in ("ln_y", "alt_x", "ln_x", "alt_y", "lag"):
                out[t] = v
    return out


def parse_het_disc_vals(raw: str) -> dict[str, list[str]]:
    """Parse flat encoded heterogeneity values from the internal env mapping."""
    if not raw or not raw.strip():
        return {}
    out: dict[str, list[str]] = {}
    for item in raw.strip().split("|"):
        item = item.strip()
        if not item or ":" not in item:
            continue
        colon = item.index(":")
        key = unquote(item[:colon].strip())
        values_raw = item[colon + 1 :].strip()
        if not key or not values_raw:
            continue
        cleaned: list[str] = []
        seen: set[str] = set()
        for value in values_raw.split(";"):
            text = unquote(value.strip())
            if not text or text in seen:
                continue
            seen.add(text)
            cleaned.append(text)
        if cleaned:
            out[key] = cleaned
    return out


def is_numeric_literal(value: str) -> bool:
    """Best-effort detection for numeric Stata literals."""
    text = value.strip()
    if not text:
        return False
    try:
        float(text)
    except ValueError:
        return False
    return True


def format_stata_eq_condition(var_name: str, raw_value: str) -> str:
    """Format a safe equality condition for Stata."""
    value = raw_value.strip()
    if is_numeric_literal(value):
        return f"{var_name}=={value}"
    escaped = value.replace('"', '""')
    return f'{var_name}=="{escaped}"'


def stata_escape(text: str) -> str:
    """Escape double quotes for Stata string literals."""
    return text.replace('"', '""')


def build_load_data_line(data_path: str) -> str:
    """Build a readable data loading line based on file suffix."""
    escaped_path = stata_escape(data_path)
    suffix = Path(data_path).suffix.lower()
    if suffix == ".dta":
        return f'use "{escaped_path}", clear'
    if suffix == ".csv":
        return f'import delimited "{escaped_path}", clear varnames(1) case(preserve)'
    if suffix in (".xls", ".xlsx"):
        return f'import excel "{escaped_path}", firstrow clear case(preserve)'
    return f'use "{escaped_path}", clear'


def build_reg_opts(panelvar: str, timevar: str, vce_option: str) -> str:
    """Build reghdfe/ivreghdfe options, omitting invalid vce(ols)."""
    absorb = f"absorb({timevar} {panelvar})"
    if vce_option == "ols":
        return absorb
    return f"{absorb} vce({vce_option})"


def unique_preserve(items: list[str]) -> list[str]:
    """Return unique non-empty items while preserving order."""
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = item.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def build_analysis_var_pool(
    *,
    y: list[str],
    x: list[str],
    cv_selected: str,
    meds: list[str],
    mods: list[str],
    heterogeneity_vars: list[str],
    iv: list[str],
    rob: dict[str, str],
    panelvar: str = "",
    timevar: str = "",
    include_panel_ids: bool = False,
) -> list[str]:
    """Build a deduplicated raw variable pool for sample anchoring or descriptive stats."""
    items: list[str] = []
    if include_panel_ids:
        items.extend([panelvar, timevar])
    items.extend(y)
    items.extend(x)
    items.extend(cv_selected.split())
    items.extend(meds)
    items.extend(mods)
    items.extend(heterogeneity_vars)
    items.extend(iv)
    items.extend(rob.get("alt_x", "").split())
    items.extend(rob.get("alt_y", "").split())
    return unique_preserve(items)


def parse_args(argv: list[str]) -> tuple[dict[str, str], int, int, str, Path]:
    import argparse

    parser = argparse.ArgumentParser(description="Generate a readable Stata .do file from JSON Starlane regression parameters.")
    parser.add_argument("--args-json", required=True, help="Path to regression_args.json")
    parser.add_argument("--selection-json", required=True, help="Path to selected_candidate.json with cv_idx and vce_idx")
    parser.add_argument("--output", required=True, help="Output .do path")
    parser.add_argument("--result-dir", default=".", help="Directory where Stata final outputs should be written")
    ns = parser.parse_args(argv[1:])
    mapping = load_regression_args_json(Path(ns.args_json))
    selection = load_selection_json(Path(ns.selection_json))
    values = {name: str(mapping[name]) for name in REGRESSION_ARG_NAMES}
    return values, int(selection["cv_idx"]), int(selection["vce_idx"]), str(ns.result_dir), Path(ns.output)


def _add_reg2docx(lines: list[str], m_start: int, m_end: int, title: str, table_num: int, replace: bool = False) -> None:
    """Append reg2docx line for models m_start..m_end. First block uses replace, rest use append."""
    models = " ".join(f"m{i}" for i in range(m_start, m_end + 1))
    tpl = BLOCK_REG2DOCX_REPLACE if replace else BLOCK_REG2DOCX_APPEND
    line = tpl.format(models=models, table_num=table_num, title=title)
    lines.append(line)


def build_do_content(
    data_path: str,
    y: list[str],
    x: list[str],
    cv_subset: str,
    panelvar: str,
    timevar: str,
    vce_option: str,
    het_disc_vals_raw: str,
    meds: list[str],
    mods: list[str],
    het_disc: list[str],
    rob: dict[str, str],
    ln_y: bool,
    ln_x: bool,
    rob_year_range: str,
    iv_raw: str,
    iv: list[str],
    export_doc: bool = False,
    result_dir: str = ".",
    expected_model_count: int | None = None,
) -> str:
    """Build full .do file content via template replacement."""
    cv = cv_subset.strip()
    lines: list[str] = []

    reg_opts = build_reg_opts(panelvar, timevar, vce_option)
    cv_selected = cv if cv else ""
    docxout = str((Path(result_dir) / "final_result.docx").as_posix())
    het_disc_vals = parse_het_disc_vals(
        het_disc_vals_raw
    )
    ln_x_sources: list[str] = []
    if ln_x:
        ln_x_sources.extend(x)
    if rob.get("ln_x"):
        ln_x_sources.extend(rob["ln_x"].split())
    ln_x_specs: list[tuple[str, str]] = []
    for source in unique_preserve(ln_x_sources):
        helper = source if source.startswith("ln") else f"ln_{source}"
        ln_x_specs.append((source, helper))

    ln_y_sources: list[str] = []
    if ln_y:
        ln_y_sources.extend(y)
    if rob.get("ln_y"):
        ln_y_sources.extend(rob["ln_y"].split())
    ln_y_specs: list[tuple[str, str]] = []
    for source in unique_preserve(ln_y_sources):
        helper = source if source.startswith("ln") else f"ln_{source}"
        ln_y_specs.append((source, helper))
    active_heterogeneity_vars = [
        group_var
        for group_var in het_disc
        if het_disc_vals.get(group_var)
    ]
    sample_pool_items = build_analysis_var_pool(
        y=y,
        x=x,
        cv_selected=cv_selected,
        meds=meds,
        mods=mods,
        heterogeneity_vars=active_heterogeneity_vars,
        iv=iv,
        rob=rob,
        panelvar=panelvar,
        timevar=timevar,
        include_panel_ids=True,
    )
    sample_pool_vars = " ".join(sample_pool_items)
    numeric_guard_vars = " ".join(sample_pool_items)
    desc_var_items = build_analysis_var_pool(
        y=y,
        x=x,
        cv_selected=cv_selected,
        meds=meds,
        mods=mods,
        heterogeneity_vars=active_heterogeneity_vars,
        iv=iv,
        rob=rob,
    )
    desc_vars = " ".join(desc_var_items)

    lines.append(f'local cv_selected "{stata_escape(cv_selected)}"')
    lines.append(f'local reg_opts "{stata_escape(reg_opts)}"')
    lines.append(f'local sample_pool_vars "{stata_escape(sample_pool_vars)}"')
    lines.append(f'local desc_vars "{stata_escape(desc_vars)}"')
    if export_doc:
        lines.append("")
        lines.append(f'local docxout "{stata_escape(docxout)}"')
        lines.extend(BLOCK_DOC_OPTS.split("\n"))
    lines.append("")
    lines.append(build_load_data_line(data_path))
    lines.append(f'local __panelvar "{panelvar}"')
    lines.append(f"capture confirm string variable {panelvar}")
    lines.append(f'if _rc == 0 egen long __panel_gid = group({panelvar}), label')
    lines.append(f'if _rc == 0 local __panelvar "__panel_gid"')
    lines.append(f'if _rc == 0 local reg_opts : subinstr local reg_opts "{panelvar}" "__panel_gid", all')
    lines.extend(BLOCK_FORCE_NUMERIC_HELPER.split("\n"))
    lines.append(f'local numeric_guard_vars "{stata_escape(numeric_guard_vars)}"')
    lines.append("local numeric_guard_vars : list uniq numeric_guard_vars")
    lines.append("foreach v of local numeric_guard_vars {")
    lines.append("\t_force_numeric_var `v'")
    lines.append("}")
    lines.append("** 全篇可比板块共用样本池")
    lines.append("egen __base_miss = rmiss(`sample_pool_vars')")
    lines.append("gen byte __base_raw_ok = (__base_miss == 0)")
    lines.append("drop __base_miss")
    lines.append("")
    lines.append(f'quietly reghdfe {y[0]} {x[0]} `cv_selected\' if __base_raw_ok, `reg_opts\'')
    lines.append("gen byte __base_sample = e(sample)")
    lines.append("drop __base_raw_ok")
    lines.append("")

    m_idx = 1
    table_num = 1

    # Baseline: nocv then cv for each (y,x)
    lines.append("** 基准回归")
    baseline_start = m_idx
    for yi in y:
        for xi in x:
            block = BLOCK_BASELINE_NOCV.format(y=yi, x=xi, m_idx=m_idx)
            lines.extend(block.split("\n"))
            m_idx += 1
    for yi in y:
        for xi in x:
            block = BLOCK_BASELINE_CV.format(y=yi, x=xi, m_idx=m_idx)
            lines.extend(block.split("\n"))
            m_idx += 1
    if export_doc:
        _add_reg2docx(lines, baseline_start, m_idx - 1, "基准回归", table_num, replace=True)
        table_num += 1
    lines.append("")

    # Robustness: alt_x
    if rob.get("alt_x"):
        lines.append("** 稳健性检验：替换X")
        block_start = m_idx
        for yi in y:
            for x_alt in rob["alt_x"].split():
                block = BLOCK_ROB_ALT_X.format(y=yi, x_alt=x_alt, m_idx=m_idx)
                lines.extend(block.split("\n"))
                m_idx += 1
        if export_doc and m_idx > block_start:
            _add_reg2docx(lines, block_start, m_idx - 1, "稳健性检验-替换X", table_num)
            table_num += 1
        lines.append("")

    # Robustness: alt_y
    if rob.get("alt_y"):
        lines.append("** 稳健性检验：替换变量")
        block_start = m_idx
        for y_alt in rob["alt_y"].split():
            for xi in x:
                block = BLOCK_ROB_ALT_Y.format(y_alt=y_alt, x=xi, m_idx=m_idx)
                lines.extend(block.split("\n"))
                m_idx += 1
        if export_doc and m_idx > block_start:
            _add_reg2docx(lines, block_start, m_idx - 1, "稳健性检验-替换变量", table_num)
            table_num += 1
        lines.append("")

    # Robustness: ln_x (auto when ln_x=yes; else only rob["ln_x"] if present)
    if ln_x_specs:
        lines.append("** 稳健性检验：X取对数")
        for source, helper in ln_x_specs:
            if helper == source:
                continue
            lines.append(f"capture drop {helper}")
            lines.append(
                f"gen double {helper} = ln({source}) if {source} > 0 & !missing({source})"
            )
        block_start = m_idx
        for yi in y:
            for _, helper in ln_x_specs:
                block = BLOCK_ROB_LN_X.format(y=yi, ln_x=helper, m_idx=m_idx)
                lines.extend(block.split("\n"))
                m_idx += 1
        if export_doc and m_idx > block_start:
            _add_reg2docx(lines, block_start, m_idx - 1, "稳健性检验-X取对数", table_num)
            table_num += 1
        lines.append("")

    # Robustness: ln_y (auto when ln_y=yes; else only rob["ln_y"] if present)
    if ln_y_specs:
        lines.append("** 稳健性检验：Y取对数")
        for source, helper in ln_y_specs:
            if helper == source:
                continue
            lines.append(f"capture drop {helper}")
            lines.append(
                f"gen double {helper} = ln({source}) if {source} > 0 & !missing({source})"
            )
        block_start = m_idx
        for _, helper in ln_y_specs:
            for xi in x:
                block = BLOCK_ROB_LN_Y.format(ln_y=helper, x=xi, m_idx=m_idx)
                lines.extend(block.split("\n"))
                m_idx += 1
        if export_doc and m_idx > block_start:
            _add_reg2docx(lines, block_start, m_idx - 1, "稳健性检验-Y取对数", table_num)
            table_num += 1
        lines.append("")

    # Robustness: lag
    if rob.get("lag"):
        lines.append("** 稳健性检验：滞后期")
        lines.append(f"tsset `__panelvar' {timevar}")
        block_start = m_idx
        for p in rob["lag"].split():
            for yi in y:
                for xi in x:
                    block = BLOCK_ROB_LAG.format(y=yi, x=xi, p=p, m_idx=m_idx)
                    lines.extend(block.split("\n"))
                    m_idx += 1
        if export_doc and m_idx > block_start:
            _add_reg2docx(lines, block_start, m_idx - 1, "稳健性检验-滞后期", table_num)
            table_num += 1
        lines.append("")

    # Robustness: year range
    if rob_year_range:
        yr_parts = rob_year_range.split(":")
        if len(yr_parts) == 2:
            yr_left, yr_right = yr_parts[0].strip(), yr_parts[1].strip()
            cond = f"{timevar} >= {yr_left} & {timevar} <= {yr_right}"
            lines.append("** 稳健性检验：时间窗口")
            block_start = m_idx
            for yi in y:
                for xi in x:
                    block = BLOCK_ROB_YEAR.format(y=yi, x=xi, cond=cond, m_idx=m_idx)
                    lines.extend(block.split("\n"))
                    m_idx += 1
            if export_doc and m_idx > block_start:
                _add_reg2docx(lines, block_start, m_idx - 1, "稳健性检验-时间窗口", table_num)
                table_num += 1
            lines.append("")

    # IV
    if iv:
        lines.append("** 工具变量检验")
        stage1_models: list[str] = []
        stage2_models: list[str] = []
        for yi in y:
            for xi in x:
                for ivv in iv:
                    block = BLOCK_IV_STAGE1.format(
                        x=xi, iv=ivv, m_idx=m_idx
                    )
                    lines.extend(block.split("\n"))
                    stage1_models.append(f"m{m_idx}")
                    m_idx += 1
                    block = BLOCK_IV_STAGE2.format(
                        y=yi, x=xi, iv=ivv, m_idx=m_idx
                    )
                    lines.extend(block.split("\n"))
                    stage2_models.append(f"m{m_idx}")
                    m_idx += 1
        if export_doc and stage1_models:
            models = " ".join(stage1_models)
            lines.append(
                f'reg2docx {models} using "`docxout\'", append `doc_common\' '
                f'title("Table {table_num}: 工具变量-一阶段") '
                f'note("Standard errors in parentheses; *** p<0.01, ** p<0.05, * p<0.1; x ~ iv + cv; IV: {stata_escape(iv_raw)}")'
            )
            table_num += 1
        if export_doc and stage2_models:
            models = " ".join(stage2_models)
            lines.append(
                f'reg2docx {models} using "`docxout\'", append `doc_common\' '
                f'title("Table {table_num}: 工具变量-二阶段 2SLS") '
                f'note("Standard errors in parentheses; *** p<0.01, ** p<0.05, * p<0.1; y ~ x_hat + cv; IV: {stata_escape(iv_raw)}")'
            )
            table_num += 1
        lines.append("")

    # Mediation: template uses the first mediation variable only.
    for med in meds[:1]:
        med_title = "中介机制"
        lines.append(f"** {med_title}：{med}")
        block_start = m_idx
        for yi in y:
            for xi in x:
                block = BLOCK_MED_TOTAL.format(y=yi, x=xi, m_idx=m_idx)
                lines.extend(block.split("\n"))
                m_idx += 1
        for xi in x:
            block = BLOCK_MED_PATH_A.format(med=med, x=xi, m_idx=m_idx)
            lines.extend(block.split("\n"))
            m_idx += 1
        if export_doc and m_idx > block_start:
            _add_reg2docx(lines, block_start, m_idx - 1, med_title, table_num)
            table_num += 1
        lines.append("")

    # Moderation
    if mods:
        lines.append("** 异质性分析：调节效应检验")
        for xi in x:
            lines.extend(BLOCK_MOD_STD_X.format(x=xi).split("\n"))
        for mod_var in mods:
            lines.extend(BLOCK_MOD_STD_MOD.format(mod=mod_var).split("\n"))
        block_start = m_idx
        for mod_var in mods:
            for yi in y:
                for xi in x:
                    block = BLOCK_MOD_REGRESS.format(
                        y=yi, x=xi, mod=mod_var, m_idx=m_idx
                    )
                    lines.extend(block.split("\n"))
                    m_idx += 1
        if export_doc and m_idx > block_start:
            _add_reg2docx(lines, block_start, m_idx - 1, "异质性分析-调节效应检验", table_num)
            table_num += 1
        lines.append("")

    # Heterogeneity: discrete groups driven by het_disc_vals
    # Same (y,x) regressions grouped together, each with all group values adjacent
    for group_var in het_disc:
        selected_values = het_disc_vals.get(group_var, [])
        if not selected_values:
            continue
        lines.append(f"** 异质性分析：离散分组-{group_var}")
        block_start = m_idx
        het_mtitles: list[str] = []
        for yi in y:
            for xi in x:
                for group_value in selected_values:
                    cond = format_stata_eq_condition(group_var, group_value)
                    block = BLOCK_HET_DISCRETE.format(
                        y=yi, x=xi, cond=cond, m_idx=m_idx
                    )
                    lines.extend(block.split("\n"))
                    het_mtitles.append(f"{group_var}={group_value}")
                    m_idx += 1
        if export_doc and m_idx > block_start:
            models = " ".join(f"m{i}" for i in range(block_start, m_idx))
            mtitles_str = " ".join(f'"{stata_escape(t)}"' for t in het_mtitles)
            lines.append(
                f'reg2docx {models} using "`docxout\'", append `doc_common_nodepvar\' '
                f'mtitles({mtitles_str}) '
                f'title("Table {table_num}: 异质性分析-离散分组-{group_var}") '
                f'note("Standard errors in parentheses; *** p<0.01, ** p<0.05, * p<0.1")'
            )
            table_num += 1
        lines.append("")

    if export_doc:
        lines.append("** 描述性统计")
        lines.append(
            'sum2docx `desc_vars\' if __base_sample using "`docxout\'", append ///\n'
            "stats(N mean(%9.3f) sd(%9.3f) min(%9.3f) median(%9.3f) max(%9.3f)) ///\n"
            "title(描述性统计)"
        )
        lines.append("")
        lines.append('di "全部结果已导出至: `docxout\'"')

    generated_model_count = m_idx - 1
    if expected_model_count is not None and generated_model_count != expected_model_count:
        raise ValueError(f"Generated Stata model count {generated_model_count} does not match ModelPlan spec count {expected_model_count}")

    return "\n".join(lines)


def main() -> int:
    try:
        values, cv_idx, vce_idx, result_dir, out = parse_args(sys.argv)

        if vce_idx < 0 or vce_idx > 3:
            raise ValueError("vce_idx must be 0-3 (0=ols, 1=robust, 2=cluster panel, 3=cluster panel+time)")

        args_proxy = RegressionArgsProxy(values)
        plan = build_model_plan(args_proxy)
        cv_subset = " ".join(plan.cv_subset(cv_idx).controls)
        vce_option = plan.vce_choice(vce_idx).stata_option
        expected_model_count = len(plan.specs_for_cv_idx(args_proxy, cv_idx))

        y_list = [v for v in values["y"].split() if v]
        x_list = [v for v in values["x"].split() if v]
        meds = [v for v in values["meds"].replace("|", " ").split() if v]
        mods = [v for v in values["mods"].replace("|", " ").split() if v]
        het_disc = [v for v in values["het_disc"].replace("|", " ").split() if v]
        iv = [v for v in values["iv"].split() if v]

        ln_y = values["ln_y"].strip().lower() in ("", "1", "是", "yes", "true")
        ln_x = values["ln_x"].strip().lower() in ("", "1", "是", "yes", "true")

        rob = parse_rob_vars(values["rob_vars"])

        raw_result_dir = result_dir.strip() if result_dir.strip() else "."
        result_dir_path = Path(raw_result_dir)
        if not result_dir_path.is_absolute():
            result_dir_path = (out.parent / result_dir_path).resolve()
        result_dir_val = str(result_dir_path)

        content = build_do_content(
            data_path=values["data_path"],
            y=y_list,
            x=x_list,
            cv_subset=cv_subset,
            panelvar=values["panelvar"],
            timevar=values["timevar"],
            vce_option=vce_option,
            het_disc_vals_raw=values["het_disc_vals"],
            meds=meds,
            mods=mods,
            het_disc=het_disc,
            rob=rob,
            ln_y=ln_y,
            ln_x=ln_x,
            rob_year_range=values["rob_year_range"].strip(),
            iv_raw=values["iv"],
            iv=iv,
            export_doc=True,
            result_dir=result_dir_val,
            expected_model_count=expected_model_count,
        )

        out.write_text(content, encoding="utf-8")
        print(f"Generated: {out}")
        return 0

    except (ValueError, IndexError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
