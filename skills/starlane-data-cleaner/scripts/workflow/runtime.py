"""Runtime helpers for starlane-data-cleaner public outputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


SKILL_NAME = "starlane-data-cleaner"
DEFAULT_ENV = "python"


def default_output_dir(root: Path) -> Path:
    return root / "output" / SKILL_NAME / DEFAULT_ENV


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, value: dict[str, Any]) -> Path:
    ensure_dir(path.parent)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
