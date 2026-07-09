"""Unified stage runner for the starlane-regression skill."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Any

from compile_plan_to_regression_args import compile_plan_to_structured_args, load_plan
from contracts import REGRESSION_ARG_NAMES, load_regression_args_json, load_selection_json
from profile_data import build_profile
from runtime import append_command, clean_success_tmp, create_run_context, mark_failed, mark_success, publish_outputs, update_manifest
from model_plan import RegressionArgsProxy, build_model_plan
from stata_emit import render_stata_model_plan_config
from verify_model_plan_drift import check_summary_header


SKILL_ROOT = Path(__file__).resolve().parents[2]
PYTHON_ENV_SCRIPTS = SKILL_ROOT / "scripts" / "envs" / "python"
STATA_ENV_SCRIPTS = SKILL_ROOT / "scripts" / "envs" / "stata"
STATA_ARG_GLOBAL_NAMES = {
    "heterogeneity_discrete_values": "het_disc_vals",
}


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


def stata_status() -> dict[str, str | bool | None]:
    stata_bin = find_stata()
    return {
        "available": bool(stata_bin),
        "path": stata_bin,
        "configured_path": os.environ.get("STARLANE_STATA_BIN"),
    }


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


def publish_run_outputs(context: Any) -> dict[str, str]:
    """Publish every file in the run's outputs/ directory to the public output dir."""
    files = sorted(path for path in context.outputs_dir.iterdir() if path.is_file())
    published = publish_outputs(context, [(path, path.name) for path in files])
    for name in published.values():
        print(f"STARLANE_PUBLISHED: {name}")
    return published


def write_stata_summary_config(path: Path, args_values: dict[str, str], export_dir: Path, tmp_dir: Path, cv_idx_start: int | None, cv_idx_end: int | None) -> None:
    lines = [
        f'global STARLANE_EXPORT "{export_dir.as_posix()}"',
        f'global STARLANE_TMP "{tmp_dir.as_posix()}"',
    ]
    for name in REGRESSION_ARG_NAMES:
        stata_name = STATA_ARG_GLOBAL_NAMES.get(name, name)
        lines.append(f'global starlane_{stata_name} {quote_stata_arg(args_values[name])}')
    lines.extend(
        [
            f'global starlane_cv_idx_start {quote_stata_arg("" if cv_idx_start is None else str(cv_idx_start))}',
            f'global starlane_cv_idx_end {quote_stata_arg("" if cv_idx_end is None else str(cv_idx_end))}',
            'global starlane_probe_only ""',
            'global starlane_csv_timestamp ""',
        ]
    )
    lines.append("")
    lines.append(render_stata_model_plan_config(build_model_plan(RegressionArgsProxy(args_values))).rstrip())
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


def command_status(ns: argparse.Namespace) -> int:
    status = {"stata": stata_status()}
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0


def command_summary(ns: argparse.Namespace) -> int:
    context = create_run_context(Path.cwd(), ns.env, "summary")
    env = {**os.environ, **context.env_vars()}
    try:
        args_path = Path(ns.args_json).resolve()
        args_values = load_regression_args_json(args_path)
        context.write_input_json("regression_args.json", args_values)
        update_manifest(
            context,
            {
                "args_json": str(args_path),
                "cv_idx_start": ns.cv_idx_start,
                "cv_idx_end": ns.cv_idx_end,
                "runtime": {
                    **context_manifest_runtime(context),
                    "skill_root": str(SKILL_ROOT),
                },
            },
        )
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
            log_path = context.logs_dir / "summary.log"
            append_command(context, cmd, log_path)
            run_command(cmd, cwd=Path.cwd(), env=env, log_path=log_path)
        else:
            stata_bin = find_stata()
            if not stata_bin:
                raise RuntimeError("No Stata binary found. Set STARLANE_STATA_BIN or install Stata.")
            config = context.generated_dir / "stata_summary_config.do"
            runner = context.generated_dir / "run_stata_summary.do"
            write_stata_summary_config(config, args_values, context.outputs_dir, context.tmp_dir, ns.cv_idx_start, ns.cv_idx_end)
            write_stata_summary_runner(runner, config)
            append_command(context, [stata_bin, "-b", "do", str(runner)], context.logs_dir / f"{runner.stem}.log")
            run_stata_batch(stata_bin, runner, context.logs_dir)

        summary_path = context.outputs_dir / "combination_summary.csv"
        if not summary_path.exists():
            raise RuntimeError(f"Summary stage finished without producing {summary_path}")
        verified_columns = check_summary_header(args_values, summary_path)
        print(f"STARLANE_PLAN_VERIFIED: {verified_columns} columns match the canonical ModelPlan")

        chunked = ns.cv_idx_start is not None or ns.cv_idx_end is not None
        if chunked:
            # Chunked runs produce partial tables; they stay in the run directory
            # and are not published as the user-facing summary.
            print(f"STARLANE_CHUNK_OUTPUT: {summary_path}")
            mark_success(context, {"summary": str(summary_path)})
        else:
            published = publish_run_outputs(context)
            mark_success(context, published)
        clean_success_tmp(context)
        return 0
    except Exception as exc:
        mark_failed(context, str(exc), traceback.format_exc())
        raise


def command_final(ns: argparse.Namespace) -> int:
    context = create_run_context(Path.cwd(), ns.env, "final")
    env = {**os.environ, **context.env_vars()}
    try:
        args_path = Path(ns.args_json).resolve()
        selection_path = Path(ns.selection_json).resolve()
        context.write_input_json("regression_args.json", load_regression_args_json(args_path))
        context.write_input_json("selected_candidate.json", load_selection_json(selection_path))
        update_manifest(
            context,
            {
                "args_json": str(args_path),
                "selection_json": str(selection_path),
                "runtime": {
                    **context_manifest_runtime(context),
                    "skill_root": str(SKILL_ROOT),
                },
            },
        )
        if ns.env == "python":
            generated_source = context.generated_dir / "regression_generated.py"
            generate_cmd = [
                sys.executable,
                str(PYTHON_ENV_SCRIPTS / "generate_final_source.py"),
                "--args-json",
                str(args_path),
                "--selection-json",
                str(selection_path),
                "--output",
                str(generated_source),
            ]
            generate_log = context.logs_dir / "generate_final_source.log"
            append_command(context, generate_cmd, generate_log)
            run_command(
                generate_cmd,
                cwd=Path.cwd(),
                env=env,
                log_path=generate_log,
            )
            final_cmd = [sys.executable, str(generated_source)]
            final_log = context.logs_dir / "final.log"
            append_command(context, final_cmd, final_log)
            run_command(final_cmd, cwd=Path.cwd(), env=env, log_path=final_log)
        else:
            stata_bin = find_stata()
            if not stata_bin:
                raise RuntimeError("No Stata binary found. Set STARLANE_STATA_BIN or install Stata.")
            generated_source = context.generated_dir / "regression_generated.do"
            generate_cmd = [
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
            ]
            generate_log = context.logs_dir / "generate_final_source.log"
            append_command(context, generate_cmd, generate_log)
            run_command(
                generate_cmd,
                cwd=Path.cwd(),
                env=env,
                log_path=generate_log,
            )
            append_command(context, [stata_bin, "-b", "do", str(generated_source)], context.logs_dir / f"{generated_source.stem}.log")
            run_stata_batch(stata_bin, generated_source, context.logs_dir)
            # The Python env copies its generated source into outputs/ itself;
            # mirror that for Stata so the published set includes the source.
            shutil.copyfile(generated_source, context.outputs_dir / generated_source.name)
        published = publish_run_outputs(context)
        mark_success(context, published)
        clean_success_tmp(context)
        return 0
    except Exception as exc:
        mark_failed(context, str(exc), traceback.format_exc())
        raise


def context_manifest_runtime(context: Any) -> dict[str, str]:
    return {
        "cwd": str(context.root),
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "estimator_backend": "pyfixest" if context.env == "python" else "stata",
    }


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

    status = sub.add_parser("status", help="Show local runtime availability")
    status.set_defaults(func=command_status)

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
