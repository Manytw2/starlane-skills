"""Unified stage runner for the starlane-regression skill."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from compile_plan_to_regression_args import compile_plan_to_structured_args, load_plan
from contracts import REGRESSION_ARG_NAMES, load_regression_args_json, load_selection_json
from profile_data import build_profile
from runtime import create_run_context, mark_failed, mark_success


SKILL_ROOT = Path(__file__).resolve().parents[2]
PYTHON_ENV_SCRIPTS = SKILL_ROOT / "scripts" / "envs" / "python"
STATA_ENV_SCRIPTS = SKILL_ROOT / "scripts" / "envs" / "stata"


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


def quote_stata_arg(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def run_command(cmd: list[str], *, cwd: Path, env: dict[str, str], log_path: Path) -> None:
    result = subprocess.run(cmd, cwd=cwd, env=env, text=True, capture_output=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "\n".join(
            [
                "$ " + " ".join(cmd),
                "",
                "STDOUT:",
                result.stdout,
                "",
                "STDERR:",
                result.stderr,
            ]
        ),
        encoding="utf-8",
    )
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {result.returncode}; see {log_path}")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_stata_summary_config(path: Path, args_values: dict[str, str], export_dir: Path, tmp_dir: Path, cv_idx_start: int | None, cv_idx_end: int | None) -> None:
    lines = [
        f'global STARLANE_EXPORT "{export_dir.as_posix()}"',
        f'global STARLANE_TMP "{tmp_dir.as_posix()}"',
    ]
    for name in REGRESSION_ARG_NAMES:
        lines.append(f'global starlane_{name} {quote_stata_arg(args_values[name])}')
    lines.extend(
        [
            f'global starlane_cv_idx_start {quote_stata_arg("" if cv_idx_start is None else str(cv_idx_start))}',
            f'global starlane_cv_idx_end {quote_stata_arg("" if cv_idx_end is None else str(cv_idx_end))}',
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
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)
    log_path = cwd / f"{do_file.stem}.log"
    if result.returncode != 0:
        detail = log_path.read_text(errors="replace")[-8000:] if log_path.exists() else ""
        raise RuntimeError(f"Stata failed with exit code {result.returncode}. {detail}")


def command_profile(ns: argparse.Namespace) -> int:
    profile = build_profile(Path(ns.input))
    text = json.dumps(profile, ensure_ascii=False, indent=2)
    if ns.output:
        out = Path(ns.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        print(f"STARLANE_PROFILE_OUTPUT: {out}")
    else:
        print(text)
    return 0


def command_compile(ns: argparse.Namespace) -> int:
    plan = load_plan(Path(ns.plan))
    structured = compile_plan_to_structured_args(plan)
    out = Path(ns.output)
    write_json(out, structured)
    print(f"STARLANE_REGRESSION_ARGS_OUTPUT: {out}")
    return 0


def command_summary(ns: argparse.Namespace) -> int:
    context = create_run_context(Path.cwd(), ns.env, "summary")
    env = {**os.environ, **context.env_vars()}
    try:
        args_path = Path(ns.args_json).resolve()
        args_values = load_regression_args_json(args_path)
        context.write_input_json("regression_args.json", args_values)
        if ns.env == "python":
            cmd = [
                sys.executable,
                str(PYTHON_ENV_SCRIPTS / "summary.py"),
                "--args-json",
                str(args_path),
            ]
            if ns.cv_idx_start is not None:
                cmd.extend(["--cv-idx-start", str(ns.cv_idx_start)])
            if ns.cv_idx_end is not None:
                cmd.extend(["--cv-idx-end", str(ns.cv_idx_end)])
            run_command(cmd, cwd=Path.cwd(), env=env, log_path=context.logs_dir / "summary.log")
        else:
            stata_bin = find_stata()
            if not stata_bin:
                raise RuntimeError("No Stata binary found. Set STARLANE_STATA_BIN or install Stata.")
            config = context.generated_dir / "stata_summary_config.do"
            runner = context.generated_dir / "run_stata_summary.do"
            write_stata_summary_config(config, args_values, context.outputs_dir, context.tmp_dir, ns.cv_idx_start, ns.cv_idx_end)
            write_stata_summary_runner(runner, config)
            run_stata_batch(stata_bin, runner, context.logs_dir)
        mark_success(context, {"summary": str(context.outputs_dir / "combination_summary.csv")})
        return 0
    except Exception as exc:
        mark_failed(context, str(exc))
        raise


def command_final(ns: argparse.Namespace) -> int:
    context = create_run_context(Path.cwd(), ns.env, "final")
    env = {**os.environ, **context.env_vars()}
    try:
        args_path = Path(ns.args_json).resolve()
        selection_path = Path(ns.selection_json).resolve()
        context.write_input_json("regression_args.json", load_regression_args_json(args_path))
        context.write_input_json("selected_candidate.json", load_selection_json(selection_path))
        if ns.env == "python":
            generated_source = context.generated_dir / "regression_generated.py"
            run_command(
                [
                    sys.executable,
                    str(PYTHON_ENV_SCRIPTS / "generate_final_source.py"),
                    "--args-json",
                    str(args_path),
                    "--selection-json",
                    str(selection_path),
                    "--output",
                    str(generated_source),
                ],
                cwd=Path.cwd(),
                env=env,
                log_path=context.logs_dir / "generate_final_source.log",
            )
            run_command([sys.executable, str(generated_source)], cwd=Path.cwd(), env=env, log_path=context.logs_dir / "final.log")
        else:
            stata_bin = find_stata()
            if not stata_bin:
                raise RuntimeError("No Stata binary found. Set STARLANE_STATA_BIN or install Stata.")
            generated_source = context.generated_dir / "regression_generated.do"
            run_command(
                [
                    sys.executable,
                    str(STATA_ENV_SCRIPTS / "generate_final_source.py"),
                    "--args-json",
                    str(args_path),
                    "--selection-json",
                    str(selection_path),
                    "--output",
                    str(generated_source),
                    "--result-dir",
                    str(context.outputs_dir),
                ],
                cwd=Path.cwd(),
                env=env,
                log_path=context.logs_dir / "generate_final_source.log",
            )
            run_stata_batch(stata_bin, generated_source, context.logs_dir)
        mark_success(context, {"outputs": str(context.outputs_dir)})
        return 0
    except Exception as exc:
        mark_failed(context, str(exc))
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run starlane-regression workflow stages.")
    sub = parser.add_subparsers(dest="stage", required=True)

    profile = sub.add_parser("profile", help="Profile an input dataset")
    profile.add_argument("--input", required=True)
    profile.add_argument("--output")
    profile.set_defaults(func=command_profile)

    compile_parser = sub.add_parser("compile", help="Compile analysis_plan to regression args")
    compile_parser.add_argument("--plan", required=True)
    compile_parser.add_argument("--output", required=True)
    compile_parser.set_defaults(func=command_compile)

    summary = sub.add_parser("summary", help="Run summary stage")
    summary.add_argument("--env", choices=("python", "stata"), required=True)
    summary.add_argument("--args-json", required=True)
    summary.add_argument("--cv-idx-start", type=int)
    summary.add_argument("--cv-idx-end", type=int)
    summary.set_defaults(func=command_summary)

    final = sub.add_parser("final", help="Run final stage")
    final.add_argument("--env", choices=("python", "stata"), required=True)
    final.add_argument("--args-json", required=True)
    final.add_argument("--selection-json", required=True)
    final.set_defaults(func=command_final)

    return parser


def main() -> int:
    parser = build_parser()
    ns = parser.parse_args()
    try:
        return ns.func(ns)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
