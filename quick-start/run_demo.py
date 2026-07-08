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
SCRIPTS = ROOT / "skills" / "starlane-regression" / "scripts"
WORKFLOW_SCRIPTS = SCRIPTS / "workflow"
PYTHON_ENV_SCRIPTS = SCRIPTS / "envs" / "python"
STATA_ENV_SCRIPTS = SCRIPTS / "envs" / "stata"
DEMO_DTA = QUICK_START / "demo.dta"
UV_PYTHON = ["uv", "run", "python"]

sys.path.insert(0, str(WORKFLOW_SCRIPTS))
from runtime import RunContext, clean_success_tmp, create_run_context, mark_failed, mark_success, publish_outputs  # noqa: E402

SUMMARY_ARGS = [
    str(DEMO_DTA),
    "lnApplyG lnGrantG",
    "Attention",
    "Scale Lev lnAge Tange Cash ROA SOE Top1 Inst",
    "Scale Lev lnAge ROA",
    "5",
    "id",
    "year",
    "Charge|Subsidy|lnCSR",
    "OverSea|lnMediaPos|lnMediaNeg",
    "",
    "",
    "alt_y:lnAGreenInv lnGGreenInv|lag:1",
    "0",
    "0",
    "",
    "Thermalinv",
    "positive",
    "",
    "",
    "",
]


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
    start = SUMMARY_ARGS[18] if len(SUMMARY_ARGS) > 18 else ""
    end = SUMMARY_ARGS[19] if len(SUMMARY_ARGS) > 19 else ""
    if start != "" and end != "":
        return out_dir / "tmp" / f"combination_summary_part_{start}_{end}.csv"
    return out_dir / "combination_summary.csv"


def print_outputs(env_name: str, paths: list[tuple[str, Path]]) -> None:
    print(f"\n{env_name} env outputs:")
    for label, path in paths:
        print(f"- {label}: {path.relative_to(ROOT)}")


def run_python_env() -> None:
    context = create_run_context(ROOT, "python", "demo")
    env = {**os.environ, **context.env_vars()}
    context.write_input_json("regression_args.json", SUMMARY_ARGS)

    try:
        print("\nRunning Python env summary...")
        run([*UV_PYTHON, str(PYTHON_ENV_SCRIPTS / "summary.py"), json.dumps(SUMMARY_ARGS, ensure_ascii=False)], env=env)

        summary_path = context.outputs_dir / "combination_summary.csv"
        first = first_summary_row(summary_path)
        final_args = [*SUMMARY_ARGS[:18], str(int(first["cv_idx"])), str(int(first["vce_idx"])), str(context.outputs_dir)]
        context.write_input_json("final_args.json", final_args)
        generated_source = context.generated_dir / "regression_generated.py"

        print("\nGenerating Python env final source...")
        run(
            [
                *UV_PYTHON,
                str(PYTHON_ENV_SCRIPTS / "generate_final_source.py"),
                json.dumps(final_args, ensure_ascii=False),
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
                (context.outputs_dir / "python_env_run_note.md", "python_env_run_note.md"),
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


def write_stata_summary_runner(path: Path, export_dir: Path, tmp_dir: Path) -> None:
    quoted = " ".join(f'"{arg}"' for arg in SUMMARY_ARGS)
    path.write_text(
        "\n".join(
            [
                f'global STARLANE_EXPORT "{export_dir.as_posix()}"',
                f'global STARLANE_TMP "{tmp_dir.as_posix()}"',
                f'do "{(STATA_ENV_SCRIPTS / "summary.do").as_posix()}" {quoted}',
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
    context.write_input_json("regression_args.json", SUMMARY_ARGS)

    try:
        print("\nRunning Stata env summary...")
        runner = context.generated_dir / "run_stata_summary.do"
        write_stata_summary_runner(runner, context.outputs_dir, context.tmp_dir)
        run_stata_batch(stata_bin, runner, context.logs_dir)

        summary_path = summary_chunk_path(context.outputs_dir)
        canonical_summary_path = context.outputs_dir / "combination_summary.csv"
        if summary_path != canonical_summary_path and summary_path.exists():
            shutil.copyfile(summary_path, canonical_summary_path)

        first = first_summary_row(canonical_summary_path)
        final_args = [*SUMMARY_ARGS[:18], str(int(first["cv_idx"])), str(int(first["vce_idx"])), str(context.outputs_dir)]
        context.write_input_json("final_args.json", final_args)
        generated_source = context.generated_dir / "regression_generated.do"

        print("\nGenerating Stata env final source...")
        run(
            [
                *UV_PYTHON,
                str(STATA_ENV_SCRIPTS / "generate_final_source.py"),
                json.dumps(final_args, ensure_ascii=False),
                str(generated_source),
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
