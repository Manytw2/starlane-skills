"""Runtime directory and manifest helpers for Starlane regression runs."""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SKILL_NAME = "starlane-regression"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def make_run_id(env: str, stage: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{env}-{stage}"


@dataclass
class RunContext:
    root: Path
    env: str
    stage: str
    run_id: str
    run_dir: Path
    inputs_dir: Path
    generated_dir: Path
    logs_dir: Path
    outputs_dir: Path
    tmp_dir: Path
    manifest_path: Path
    public_output_dir: Path

    def env_vars(self) -> dict[str, str]:
        return {
            "STARLANE_EXPORT": str(self.outputs_dir),
            "STARLANE_TMP": str(self.tmp_dir),
            "STARLANE_PROGRESS_LOG": str(self.logs_dir / "progress.jsonl"),
        }

    def relative_paths(self) -> dict[str, str]:
        def rel(path: Path) -> str:
            try:
                return str(path.relative_to(self.root))
            except ValueError:
                return str(path)

        return {
            "run_dir": rel(self.run_dir),
            "inputs": rel(self.inputs_dir),
            "generated": rel(self.generated_dir),
            "logs": rel(self.logs_dir),
            "outputs": rel(self.outputs_dir),
            "tmp": rel(self.tmp_dir),
            "public_output": rel(self.public_output_dir),
        }

    def write_input_json(self, name: str, value: Any) -> Path:
        path = self.inputs_dir / name
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path


def create_run_context(root: Path, env: str, stage: str, run_id: str | None = None) -> RunContext:
    root = root.resolve()
    run_id = run_id or make_run_id(env, stage)
    run_dir = root / ".starlane" / "runtime" / SKILL_NAME / "runs" / run_id
    context = RunContext(
        root=root,
        env=env,
        stage=stage,
        run_id=run_id,
        run_dir=run_dir,
        inputs_dir=run_dir / "inputs",
        generated_dir=run_dir / "generated",
        logs_dir=run_dir / "logs",
        outputs_dir=run_dir / "outputs",
        tmp_dir=run_dir / "tmp",
        manifest_path=run_dir / "run.json",
        public_output_dir=root / "output" / SKILL_NAME,
    )
    for path in (
        context.inputs_dir,
        context.generated_dir,
        context.logs_dir,
        context.outputs_dir,
        context.tmp_dir,
        context.public_output_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)
    write_manifest(
        context,
        status="running",
        extra={
            "started_at": utc_now(),
            "logs": default_logs(context),
            "commands": [],
            "runtime": {
                "cwd": str(root),
                "python_executable": sys.executable,
                "python_version": sys.version.split()[0],
                "estimator_backend": "pyfixest" if env == "python" else "stata",
            },
        },
    )
    return context


def read_manifest(context: RunContext) -> dict[str, Any]:
    if not context.manifest_path.exists():
        return {}
    return json.loads(context.manifest_path.read_text(encoding="utf-8"))


def write_manifest(context: RunContext, status: str, extra: dict[str, Any] | None = None) -> None:
    data = read_manifest(context)
    data.update(
        {
            "run_id": context.run_id,
            "skill": SKILL_NAME,
            "env": context.env,
            "stage": context.stage,
            "status": status,
            "paths": context.relative_paths(),
        }
    )
    if extra:
        data.update(extra)
    context.manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_manifest(context: RunContext, extra: dict[str, Any]) -> None:
    write_manifest(context, status=read_manifest(context).get("status", "running"), extra=extra)


def append_command(context: RunContext, cmd: list[str], log_path: Path) -> None:
    data = read_manifest(context)
    commands = data.get("commands", [])
    if not isinstance(commands, list):
        commands = []
    commands.append(
        {
            "cmd": cmd,
            "log": relative_to_root(context, log_path),
        }
    )
    update_manifest(context, {"commands": commands})


def relative_to_root(context: RunContext, path: Path) -> str:
    try:
        return str(path.relative_to(context.root))
    except ValueError:
        return str(path)


def default_logs(context: RunContext) -> dict[str, str]:
    logs = {"progress": relative_to_root(context, context.logs_dir / "progress.jsonl")}
    if context.stage == "summary":
        logs["summary"] = relative_to_root(context, context.logs_dir / "summary.log")
    if context.stage == "final":
        logs["generate_final_source"] = relative_to_root(context, context.logs_dir / "generate_final_source.log")
        logs["final"] = relative_to_root(context, context.logs_dir / "final.log")
    return logs


def mark_success(context: RunContext, outputs: dict[str, str] | None = None) -> None:
    write_manifest(context, status="success", extra={"ended_at": utc_now(), "outputs": outputs or {}})


def mark_failed(context: RunContext, error: str, traceback_text: str | None = None) -> None:
    extra: dict[str, Any] = {"ended_at": utc_now(), "error": error}
    if traceback_text:
        extra["traceback"] = traceback_text
    write_manifest(context, status="failed", extra=extra)


def publish_outputs(context: RunContext, mappings: list[tuple[Path, str]]) -> dict[str, str]:
    published: dict[str, str] = {}
    context.public_output_dir.mkdir(parents=True, exist_ok=True)
    for source, name in mappings:
        if not source.exists():
            continue
        target = context.public_output_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        published[name] = str(target.relative_to(context.root))
    return published


def clean_success_tmp(context: RunContext) -> None:
    if context.tmp_dir.exists():
        shutil.rmtree(context.tmp_dir)
