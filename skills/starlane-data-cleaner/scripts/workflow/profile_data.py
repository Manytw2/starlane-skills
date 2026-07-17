"""profile stage: input declarations → data profile.

IN:  inputs_json   input file declarations
OUT: profile.json  rows, columns, types, missingness, and key diagnostics
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parents[1]
REPO_ROOT = SKILL_ROOT.parents[1]
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

from scripts.envs.python.diagnostics import dataframe_profile  # noqa: E402
from scripts.envs.python.io import read_data  # noqa: E402
from scripts.workflow.contracts import require_list, require_mapping, resolve_path  # noqa: E402
from scripts.workflow.runtime import default_output_dir, ensure_dir, file_sha256, write_json  # noqa: E402


def profile_inputs(inputs_json: Path, cwd: Path, output_dir: Path | None = None) -> dict[str, Any]:
    data = json.loads(inputs_json.read_text(encoding="utf-8"))
    inputs = require_list(data.get("inputs", data), "inputs")
    profiles: list[dict[str, Any]] = []
    for idx, item in enumerate(inputs):
        input_item = require_mapping(item, f"inputs[{idx}]")
        name = input_item["name"]
        path = resolve_path(input_item["path"], cwd)
        df = read_data(path)
        profile = dataframe_profile(name, df, input_item.get("key"))
        profile["path"] = str(path)
        profile["sha256"] = file_sha256(path)
        profiles.append(profile)

    result = {"inputs": profiles}
    target_dir = output_dir or default_output_dir(REPO_ROOT)
    ensure_dir(target_dir)
    write_json(target_dir / "profile.json", result)
    return result
