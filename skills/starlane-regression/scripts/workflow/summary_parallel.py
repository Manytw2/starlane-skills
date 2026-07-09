"""Chunked summary-stage orchestration shared by the Python and Stata envs.

`run_stage.py summary` always delegates here; serial execution is the K=1
degenerate case (one chunk spanning the whole cv-subset range), so both envs
share one pipeline: warmup -> chunk -> dispatch -> merge/finalize.

Scheduling uses guided self-scheduling (factoring): chunk sizes decrease as
work drains, so large chunks amortize worker startup cost while small tail
chunks smooth the load imbalance caused by baseline-gate pruning.
"""

from __future__ import annotations

import csv
import json
import math
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from model_plan import RegressionArgsProxy, build_model_plan
from runtime import RunContext, append_command, update_manifest
from stata_config import render_stata_summary_config, render_stata_summary_runner
from verify_model_plan_drift import check_summary_header


SKILL_ROOT = Path(__file__).resolve().parents[2]
PYTHON_ENV_SCRIPTS = SKILL_ROOT / "scripts" / "envs" / "python"

# Workers must not multiply threads on top of process-level parallelism.
# VECLIB covers macOS Accelerate; NUMBA covers pyfixest's JIT kernels.
PYTHON_WORKER_THREAD_CAPS = {
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "NUMBA_NUM_THREADS": "1",
}

# Minimum cv subsets per chunk. Stata pays a full batch-instance start plus
# data load per chunk, so its floor is higher.
MIN_CHUNK_SUBSETS = {"python": 1, "stata": 2}

# Rough per-worker memory model for the jobs budget: input size scaled by an
# in-memory expansion factor per format, plus the runtime baseline
# (interpreter + estimator packages for Python, Stata itself for Stata).
WORKER_BASE_MEMORY_BYTES = {"python": 300 * 1024**2, "stata": 200 * 1024**2}
INPUT_MEMORY_FACTOR = {".dta": 2.0, ".csv": 2.0, ".xls": 5.0, ".xlsx": 5.0}
AVAILABLE_MEMORY_USE_RATIO = 0.6

POLL_INTERVAL_SECONDS = 0.2
TERMINATE_GRACE_SECONDS = 5.0
LOG_TAIL_CHARS = 8000

SUMMARY_CSV_NAME = "combination_summary.csv"


class JsonlLogger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def event(self, event: str, **fields: object) -> None:
        payload = {"event": event, **fields}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


@dataclass(frozen=True)
class Chunk:
    cv_start: int
    cv_end: int

    @property
    def subset_count(self) -> int:
        return self.cv_end - self.cv_start + 1

    @property
    def tag(self) -> str:
        return f"chunk_{self.cv_start}_{self.cv_end}"


@dataclass
class ChunkJob:
    chunk: Chunk
    popen: subprocess.Popen
    log_handle: object
    log_path: Path
    part_path: Path


def detect_available_memory_bytes() -> int | None:
    try:
        if sys.platform == "darwin":
            vm_stat = subprocess.run(["vm_stat"], capture_output=True, text=True, check=True).stdout
            page_size_match = re.search(r"page size of (\d+) bytes", vm_stat)
            if not page_size_match:
                return None
            page_size = int(page_size_match.group(1))
            pages = 0
            for line in vm_stat.splitlines():
                name, _, value = line.partition(":")
                if name.strip().lower() in ("pages free", "pages inactive"):
                    pages += int(value.strip().rstrip("."))
            return pages * page_size if pages else None
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) * 1024
    except Exception:
        return None
    return None


def estimate_worker_memory_bytes(env: str, input_path: str) -> int:
    path = Path(input_path)
    factor = INPUT_MEMORY_FACTOR.get(path.suffix.lower(), 2.0)
    try:
        input_size = path.stat().st_size
    except OSError:
        input_size = 0
    return int(input_size * factor) + WORKER_BASE_MEMORY_BYTES[env]


def compute_auto_jobs(env: str, input_path: str, task_count: int) -> tuple[int, str]:
    """Return (jobs, human-readable decision detail) from three budgets."""
    try:
        cores = os.cpu_count() or 1
        reserve = 1 if cores <= 4 else 2
        cores_budget = max(1, cores - reserve)

        available = detect_available_memory_bytes()
        if available is None:
            memory_budget = None
            memory_note = "mem=unknown"
        else:
            per_worker = estimate_worker_memory_bytes(env, input_path)
            memory_budget = max(1, int(available * AVAILABLE_MEMORY_USE_RATIO // per_worker))
            memory_note = f"mem_cap={memory_budget}"

        budgets = [cores_budget, task_count]
        if memory_budget is not None:
            budgets.append(memory_budget)
        jobs = max(1, min(budgets))
        return jobs, f"cores={cores} reserve={reserve}, {memory_note}, tasks={task_count}"
    except Exception as exc:
        cores = os.cpu_count() or 1
        return max(1, min(4, cores)), f"fallback after probe error: {exc}"


def build_chunks(cv_start: int, cv_end: int, jobs: int, min_chunk: int) -> list[Chunk]:
    """Guided self-scheduling chunk list: sizes decay as remaining work drains."""
    total = cv_end - cv_start + 1
    if jobs <= 1:
        return [Chunk(cv_start, cv_end)]
    chunks: list[Chunk] = []
    start = cv_start
    remaining = total
    while remaining > 0:
        size = min(remaining, max(min_chunk, math.ceil(remaining / (2 * jobs))))
        chunks.append(Chunk(start, start + size - 1))
        start += size
        remaining -= size
    return chunks


def tail_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(errors="replace")[-LOG_TAIL_CHARS:]


def prepare_input_cache(
    env: str,
    args_values: dict[str, str],
    context: RunContext,
    stata_bin: str | None,
    jsonl: JsonlLogger,
) -> str | None:
    """Parse slow spreadsheet input once so K workers read a fast cache.

    Returns the cache path to use as worker input, or None to keep the
    original input. dta/csv inputs are cheap to load and skip warmup.
    """
    input_path = args_values["data_path"]
    suffix = Path(input_path).suffix.lower()
    if suffix not in (".xls", ".xlsx"):
        return None
    jsonl.event("summary_input_warmup_started", input=input_path, env=env)
    if env == "python":
        import pandas as pd

        cache = context.tmp_dir / "input_cache.pkl"
        pd.read_excel(input_path).to_pickle(cache)
    else:
        cache = context.tmp_dir / "input_cache.dta"
        config = context.generated_dir / "stata_summary_config_probe.do"
        runner = context.generated_dir / "run_stata_summary_probe.do"
        config.write_text(
            render_stata_summary_config(
                args_values,
                export_dir=context.outputs_dir,
                tmp_dir=context.tmp_dir,
                probe_only=True,
                cache_dta=cache,
            ),
            encoding="utf-8",
        )
        runner.write_text(render_stata_summary_runner(config), encoding="utf-8")
        cmd = [str(stata_bin), "-b", "do", str(runner)]
        append_command(context, cmd, context.logs_dir / f"{runner.stem}.log")
        result = subprocess.run(cmd, cwd=context.logs_dir, env=os.environ.copy(), text=True, capture_output=True)
        if result.returncode != 0 or not cache.exists():
            detail = tail_text(context.logs_dir / f"{runner.stem}.log")
            raise RuntimeError(f"Stata warmup probe failed with exit code {result.returncode}. {detail}")
    jsonl.event("summary_input_warmup_done", cache=str(cache))
    return str(cache)


def start_python_chunk(
    chunk: Chunk,
    *,
    context: RunContext,
    worker_args_json: Path,
) -> ChunkJob:
    chunk_dir = context.tmp_dir / "chunks" / chunk.tag
    chunk_dir.mkdir(parents=True, exist_ok=True)
    log_dir = context.logs_dir / "chunks"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{chunk.tag}.log"
    env = {
        **os.environ,
        **PYTHON_WORKER_THREAD_CAPS,
        "STARLANE_EXPORT": str(chunk_dir),
        "STARLANE_TMP": str(chunk_dir),
        "STARLANE_PROGRESS_LOG": str(log_dir / f"{chunk.tag}.progress.jsonl"),
    }
    cmd = [
        sys.executable,
        str(PYTHON_ENV_SCRIPTS / "build_summary.py"),
        "--args-json",
        str(worker_args_json),
        "--cv-idx-start",
        str(chunk.cv_start),
        "--cv-idx-end",
        str(chunk.cv_end),
    ]
    append_command(context, cmd, log_path)
    handle = log_path.open("w", encoding="utf-8")
    handle.write("$ " + " ".join(cmd) + "\n\n")
    handle.flush()
    popen = subprocess.Popen(cmd, cwd=context.root, env=env, stdout=handle, stderr=subprocess.STDOUT, text=True)
    return ChunkJob(
        chunk=chunk,
        popen=popen,
        log_handle=handle,
        log_path=log_path,
        part_path=chunk_dir / SUMMARY_CSV_NAME,
    )


def start_stata_chunk(
    chunk: Chunk,
    *,
    context: RunContext,
    worker_args_values: dict[str, str],
    stata_bin: str,
) -> ChunkJob:
    chunk_dir = context.tmp_dir / "chunks" / chunk.tag
    # Concurrent Stata instances must not share a temp dir: tempfile/preserve
    # would overwrite each other (see the parallel package's 1.14 fix).
    statatmp_dir = chunk_dir / "statatmp"
    statatmp_dir.mkdir(parents=True, exist_ok=True)
    log_dir = context.logs_dir / "chunks"
    log_dir.mkdir(parents=True, exist_ok=True)

    config = context.generated_dir / f"stata_summary_config_{chunk.tag}.do"
    runner = context.generated_dir / f"run_stata_summary_{chunk.tag}.do"
    config.write_text(
        render_stata_summary_config(
            worker_args_values,
            export_dir=chunk_dir,
            tmp_dir=chunk_dir,
            cv_idx_start=chunk.cv_start,
            cv_idx_end=chunk.cv_end,
        ),
        encoding="utf-8",
    )
    runner.write_text(render_stata_summary_runner(config, single_processor=True), encoding="utf-8")

    log_path = log_dir / f"{runner.stem}.log"
    env = {**os.environ, "STATATMP": str(statatmp_dir)}
    cmd = [stata_bin, "-b", "do", str(runner)]
    append_command(context, cmd, log_path)
    handle = log_path.with_suffix(".console.log").open("w", encoding="utf-8")
    handle.write("$ " + " ".join(cmd) + "\n\n")
    handle.flush()
    popen = subprocess.Popen(cmd, cwd=log_dir, env=env, stdout=handle, stderr=subprocess.STDOUT, text=True)
    return ChunkJob(
        chunk=chunk,
        popen=popen,
        log_handle=handle,
        log_path=log_path,
        part_path=chunk_dir / f"combination_summary_part_{chunk.cv_start}_{chunk.cv_end}.csv",
    )


def terminate_jobs(jobs: list[ChunkJob]) -> None:
    for job in jobs:
        if job.popen.poll() is None:
            job.popen.terminate()
    deadline = time.monotonic() + TERMINATE_GRACE_SECONDS
    for job in jobs:
        try:
            job.popen.wait(timeout=max(0.1, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            job.popen.kill()
            job.popen.wait()
    for job in jobs:
        job.log_handle.close()


def run_chunks(
    chunks: list[Chunk],
    jobs: int,
    start_chunk,
    jsonl: JsonlLogger,
    total_subsets: int,
) -> list[tuple[Chunk, Path]]:
    pending = list(chunks)
    running: list[ChunkJob] = []
    parts: list[tuple[Chunk, Path]] = []
    done_subsets = 0
    try:
        while pending or running:
            while pending and len(running) < jobs:
                job = start_chunk(pending.pop(0))
                jsonl.event(
                    "chunk_started",
                    chunk=job.chunk.tag,
                    cv_start=job.chunk.cv_start,
                    cv_end=job.chunk.cv_end,
                    running=len(running) + 1,
                )
                running.append(job)
            time.sleep(POLL_INTERVAL_SECONDS)
            still_running: list[ChunkJob] = []
            for job in running:
                returncode = job.popen.poll()
                if returncode is None:
                    still_running.append(job)
                    continue
                job.log_handle.close()
                if returncode != 0:
                    raise RuntimeError(
                        f"Summary chunk {job.chunk.tag} failed with exit code {returncode}. "
                        f"See {job.log_path}. {tail_text(job.log_path)}"
                    )
                if not job.part_path.exists():
                    raise RuntimeError(
                        f"Summary chunk {job.chunk.tag} finished without producing {job.part_path}. See {job.log_path}."
                    )
                parts.append((job.chunk, job.part_path))
                done_subsets += job.chunk.subset_count
                jsonl.event(
                    "chunk_completed",
                    chunk=job.chunk.tag,
                    completed_subsets=done_subsets,
                    total_subsets=total_subsets,
                    percent_complete=round(done_subsets / total_subsets * 100, 2) if total_subsets else 100.0,
                )
            running = still_running
        return parts
    except Exception:
        terminate_jobs(running)
        raise


def merge_parts(parts: list[tuple[Chunk, Path]], output_path: Path) -> int:
    header: list[str] | None = None
    rows: list[dict[str, str]] = []
    for chunk, path in sorted(parts, key=lambda item: item[0].cv_start):
        with path.open(newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            part_header = next(reader, [])
            if header is None:
                header = part_header
            elif part_header != header:
                raise RuntimeError(f"Summary part header mismatch in {path}")
            for row in reader:
                if len(row) != len(part_header):
                    raise RuntimeError(
                        f"Summary row width drift in {path}: header has {len(part_header)} columns "
                        f"but a row has {len(row)} cells. The env ran sections outside the canonical ModelPlan."
                    )
                rows.append(dict(zip(part_header, row)))
    if header is None:
        raise RuntimeError("Summary produced no part tables to merge")

    seen: set[str] = set()
    for row in rows:
        selection_id = row.get("selection_id", "")
        if selection_id in seen:
            raise RuntimeError(f"Duplicate selection_id {selection_id!r} across summary parts")
        seen.add(selection_id)

    rows.sort(key=lambda r: (-float(r["score"] or 0), int(r["cv_idx"]), int(r["vce_idx"])))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def run_summary(
    *,
    context: RunContext,
    env: str,
    args_values: dict[str, str],
    args_path: Path,
    cv_idx_start: int | None,
    cv_idx_end: int | None,
    stata_bin: str | None,
) -> Path:
    jsonl = JsonlLogger(context.logs_dir / "progress.jsonl")
    plan = build_model_plan(RegressionArgsProxy(args_values))
    n_valid = len(plan.cv_subsets)
    if n_valid == 0:
        raise RuntimeError("No valid cv subsets. Check cv_fixed and cv_min_count.")

    explicit_range = cv_idx_start is not None or cv_idx_end is not None
    if explicit_range:
        if cv_idx_start is None or cv_idx_end is None:
            raise RuntimeError("Provide both --cv-idx-start and --cv-idx-end for a chunked summary run.")
        if not (0 <= cv_idx_start <= cv_idx_end < n_valid):
            raise RuntimeError(f"cv range [{cv_idx_start}, {cv_idx_end}] is out of bounds for {n_valid} cv subsets.")
        lo, hi = cv_idx_start, cv_idx_end
        # An explicit range means an outer caller already schedules chunks;
        # run it as one chunk to avoid nested parallelism.
        jobs, jobs_detail = 1, "explicit cv range runs as one externally scheduled chunk"
    else:
        lo, hi = 0, n_valid - 1
        jobs, jobs_detail = compute_auto_jobs(env, args_values["data_path"], n_valid)
    print(f"STARLANE_JOBS: auto -> {jobs} ({jobs_detail})")

    chunks = build_chunks(lo, hi, jobs, MIN_CHUNK_SUBSETS[env])
    total_subsets = hi - lo + 1
    jsonl.event(
        "summary_parallel_plan",
        env=env,
        jobs=jobs,
        jobs_detail=jobs_detail,
        total_subsets=total_subsets,
        chunks=[[c.cv_start, c.cv_end] for c in chunks],
    )
    update_manifest(
        context,
        {
            "parallel": {
                "jobs": jobs,
                "jobs_detail": jobs_detail,
                "chunks": [[c.cv_start, c.cv_end] for c in chunks],
            }
        },
    )

    worker_args_values = args_values
    worker_args_json = args_path
    if len(chunks) > 1:
        cache_path = prepare_input_cache(env, args_values, context, stata_bin, jsonl)
        if cache_path is not None:
            worker_args_values = {**args_values, "data_path": cache_path}
            if env == "python":
                structured = json.loads(args_path.read_text(encoding="utf-8"))
                structured["data_path"] = cache_path
                worker_args_json = context.generated_dir / "regression_args_worker.json"
                worker_args_json.write_text(
                    json.dumps(structured, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )

    if env == "python":
        def start_chunk(chunk: Chunk) -> ChunkJob:
            return start_python_chunk(chunk, context=context, worker_args_json=worker_args_json)
    else:
        def start_chunk(chunk: Chunk) -> ChunkJob:
            return start_stata_chunk(chunk, context=context, worker_args_values=worker_args_values, stata_bin=str(stata_bin))

    parts = run_chunks(chunks, jobs, start_chunk, jsonl, total_subsets)

    jsonl.event("finalize_started", parts=len(parts))
    summary_path = context.outputs_dir / SUMMARY_CSV_NAME
    row_count = merge_parts(parts, summary_path)
    verified_columns = check_summary_header(args_values, summary_path)
    print(f"STARLANE_PLAN_VERIFIED: {verified_columns} columns match the canonical ModelPlan")
    jsonl.event("finalize_done", rows=row_count, path=str(summary_path))
    print(f"STARLANE_OUTPUT: {summary_path}")
    return summary_path
