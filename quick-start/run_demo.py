"""Run the Starlane regression quick-start demo."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUICK_START = Path(__file__).resolve().parent
SKILL_ROOT = ROOT / "skills" / "starlane-regression"
SCRIPTS = SKILL_ROOT / "scripts"
WORKFLOW_SCRIPTS = SCRIPTS / "workflow"
PYTHON_ENV_SCRIPTS = SCRIPTS / "envs" / "python"
STATA_ENV_SCRIPTS = SCRIPTS / "envs" / "stata"
DEMO_DTA = QUICK_START / "demo.dta"
UV_PYTHON = ["uv", "run", "--project", str(SKILL_ROOT), "python"]

sys.path.insert(0, str(WORKFLOW_SCRIPTS))
from runtime import RunContext, clean_success_tmp, create_run_context, mark_failed, mark_success, publish_outputs  # noqa: E402

SUMMARY_ARGS = {
    "input_dta": str(DEMO_DTA),
    "outcomes": ["lnApplyG", "lnGrantG"],
    "explanatory_vars": ["Attention"],
    "controls": {
        "search_pool": ["Scale", "Lev", "lnAge", "Tange", "Cash", "ROA", "SOE", "Top1", "Inst"],
        "always_include": ["Scale", "Lev", "lnAge", "ROA"],
        "min_count": 5,
    },
    "panel": {
        "entity": "id",
        "time": "year",
    },
    "robustness": {
        "alternative_outcomes": ["lnAGreenInv", "lnGGreenInv"],
        "alternative_explanatory_vars": [],
        "lag_periods": [1],
        "log_y": False,
        "log_x": False,
        "sample_window": None,
    },
    "mechanism": {
        "variables": ["Charge", "Subsidy", "lnCSR"],
    },
    "moderation": {
        "variables": ["OverSea", "lnMediaPos", "lnMediaNeg"],
    },
    "heterogeneity": {
        "discrete_groups": [],
        "selected_values": {},
    },
    "iv": {
        "instruments": ["Thermalinv"],
    },
    "execution": {
        "coef_direction": "positive",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Starlane quick-start demo.")
    parser.add_argument(
        "--env",
        choices=("python", "stata", "both"),
        default="python",
        help="Execution env to run. Defaults to python.",
    )
    return parser.parse_args()


def run(cmd: list[str], env: dict[str, str] | None = None, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, cwd=cwd, env=env, text=True, capture_output=True)
    if result.returncode != 0:
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        raise SystemExit(result.returncode)
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)
    return result


def find_stata() -> str | None:
    configured = os.environ.get("STARLANE_STATA_BIN")
    candidates = [
        configured,
        "/Applications/Stata/StataMP.app/Contents/MacOS/stata-mp",
        "/Applications/Stata/StataMP.app/Contents/MacOS/StataMP",
        "stata-mp",
        "stata-se",
        "stata",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        if Path(candidate).exists() or shutil.which(candidate):
            return candidate
    return None


def first_summary_row(summary_path: Path) -> dict[str, str]:
    with summary_path.open(newline="", encoding="utf-8") as f:
        rows = csv.DictReader(f)
        first = next(rows, None)
    if first is None:
        raise SystemExit(f"No rows were produced in {summary_path}")
    return first


def summary_chunk_path(out_dir: Path) -> Path:
    return out_dir / "combination_summary.csv"


def print_outputs(env_name: str, paths: list[tuple[str, Path]]) -> None:
    print(f"\n{env_name} env outputs:")
    for label, path in paths:
        print(f"- {label}: {path.relative_to(ROOT)}")


def run_python_env() -> None:
    context = create_run_context(ROOT, "python", "demo")
    env = {**os.environ, **context.env_vars()}
    args_json = context.write_input_json("regression_args.json", SUMMARY_ARGS)

    try:
        print("\nRunning Python env summary...")
        run([*UV_PYTHON, str(PYTHON_ENV_SCRIPTS / "summary.py"), "--args-json", str(args_json)], env=env)

        summary_path = context.outputs_dir / "combination_summary.csv"
        first = first_summary_row(summary_path)
        selection_json = context.write_input_json("selected_candidate.json", {"cv_idx": int(first["cv_idx"]), "vce_idx": int(first["vce_idx"])})
        generated_source = context.generated_dir / "regression_generated.py"

        print("\nGenerating Python env final source...")
        run(
            [
                *UV_PYTHON,
                str(PYTHON_ENV_SCRIPTS / "generate_final_source.py"),
                "--args-json",
                str(args_json),
                "--selection-json",
                str(selection_json),
                "--output",
                str(generated_source),
            ],
            env=env,
        )

        print("\nRunning Python env final source...")
        run([*UV_PYTHON, str(generated_source)], env=env)

        published = publish_outputs(
            context,
            [
                (summary_path, "combination_summary.csv"),
                (generated_source, "regression_generated.py"),
                (context.outputs_dir / "final_result.csv", "final_result.csv"),
                (context.outputs_dir / "final_result.md", "final_result.md"),
                (context.outputs_dir / "final_result.docx", "final_result.docx"),
            ],
        )
        clean_success_tmp(context)
        mark_success(context, published)

        print_outputs(
            "Python",
            [
                ("summary CSV", context.public_output_dir / "combination_summary.csv"),
                ("generated source", context.public_output_dir / "regression_generated.py"),
                ("result CSV", context.public_output_dir / "final_result.csv"),
                ("Markdown report", context.public_output_dir / "final_result.md"),
                ("Word report", context.public_output_dir / "final_result.docx"),
            ],
        )
    except Exception as exc:
        mark_failed(context, str(exc))
        raise


def quote_stata_arg(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def write_stata_summary_config(path: Path, args_values: dict[str, str], export_dir: Path, tmp_dir: Path) -> None:
    from contracts import REGRESSION_ARG_NAMES, validate_regression_args

    flat_args = validate_regression_args(args_values)
    lines = [
        f'global STARLANE_EXPORT "{export_dir.as_posix()}"',
        f'global STARLANE_TMP "{tmp_dir.as_posix()}"',
    ]
    for name in REGRESSION_ARG_NAMES:
        lines.append(f'global starlane_{name} {quote_stata_arg(flat_args[name])}')
    lines.extend(
        [
            'global starlane_cv_idx_start ""',
            'global starlane_cv_idx_end ""',
            'global starlane_probe_only ""',
            'global starlane_csv_timestamp ""',
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_stata_summary_runner(path: Path, config_path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                f'do "{config_path.as_posix()}"',
                f'do "{(STATA_ENV_SCRIPTS / "summary.do").as_posix()}"',
                "exit",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def run_stata_batch(stata_bin: str, do_file: Path, cwd: Path) -> None:
    result = subprocess.run([stata_bin, "-b", "do", str(do_file)], cwd=cwd, text=True, capture_output=True)
    if result.returncode != 0:
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        log_path = cwd / f"{do_file.stem}.log"
        if log_path.exists():
            print(log_path.read_text(errors="replace")[-8000:], file=sys.stderr)
        raise SystemExit(result.returncode)


def run_stata_env() -> None:
    stata_bin = find_stata()
    if not stata_bin:
        raise SystemExit(
            "Stata env was selected, but no Stata binary was found. "
            "Install Stata or set STARLANE_STATA_BIN to the Stata executable path."
        )

    context = create_run_context(ROOT, "stata", "demo")
    args_json = context.write_input_json("regression_args.json", SUMMARY_ARGS)

    try:
        print("\nRunning Stata env summary...")
        config = context.generated_dir / "stata_summary_config.do"
        runner = context.generated_dir / "run_stata_summary.do"
        write_stata_summary_config(config, SUMMARY_ARGS, context.outputs_dir, context.tmp_dir)
        write_stata_summary_runner(runner, config)
        run_stata_batch(stata_bin, runner, context.logs_dir)

        summary_path = summary_chunk_path(context.outputs_dir)
        canonical_summary_path = context.outputs_dir / "combination_summary.csv"
        if summary_path != canonical_summary_path and summary_path.exists():
            shutil.copyfile(summary_path, canonical_summary_path)

        first = first_summary_row(canonical_summary_path)
        selection_json = context.write_input_json("selected_candidate.json", {"cv_idx": int(first["cv_idx"]), "vce_idx": int(first["vce_idx"])})
        generated_source = context.generated_dir / "regression_generated.do"

        print("\nGenerating Stata env final source...")
        run(
            [
                *UV_PYTHON,
                str(STATA_ENV_SCRIPTS / "generate_final_source.py"),
                "--args-json",
                str(args_json),
                "--selection-json",
                str(selection_json),
                "--output",
                str(generated_source),
                "--result-dir",
                str(context.outputs_dir),
            ]
        )

        print("\nRunning Stata env final source...")
        run_stata_batch(stata_bin, generated_source, context.logs_dir)

        published = publish_outputs(
            context,
            [
                (canonical_summary_path, "combination_summary.csv"),
                (generated_source, "regression_generated.do"),
                (context.outputs_dir / "starlane-regression-results.docx", "starlane-regression-results.docx"),
            ],
        )
        clean_success_tmp(context)
        mark_success(context, published)

        print_outputs(
            "Stata",
            [
                ("summary CSV", context.public_output_dir / "combination_summary.csv"),
                ("generated source", context.public_output_dir / "regression_generated.do"),
                ("Word report", context.public_output_dir / "starlane-regression-results.docx"),
            ],
        )
    except Exception as exc:
        mark_failed(context, str(exc))
        raise


def main() -> int:
    args = parse_args()
    if not DEMO_DTA.exists():
        raise SystemExit(f"Demo dataset not found: {DEMO_DTA}")

    if args.env in ("python", "both"):
        run_python_env()
    if args.env in ("stata", "both"):
        run_stata_env()

    print("\nQuick start complete. Output root: output/starlane-regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
