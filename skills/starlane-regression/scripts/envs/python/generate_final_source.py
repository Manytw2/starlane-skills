"""Final stage (python env): regression args + selection -> 可复现源码.

IN:  regression_args.json + selected_candidate.json（cv_idx / vce_idx）
OUT: 生成的 Python 源码（运行后产出 final_result.* 到 STARLANE_EXPORT）
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from common import load_regression_args_json, load_selection_json


def parse_args(argv: list[str]) -> tuple[dict[str, str], int, int, Path, Path]:
    import argparse

    parser = argparse.ArgumentParser(description="Generate a runnable Starlane Python final-stage source file.")
    parser.add_argument("--args-json", required=True, help="Path to regression_args.json")
    parser.add_argument("--selection-json", required=True, help="Path to selected_candidate.json with cv_idx and vce_idx")
    parser.add_argument("--output", required=True, help="Output generated Python source path")
    ns = parser.parse_args(argv[1:])
    values = load_regression_args_json(ns.args_json)
    selection = load_selection_json(ns.selection_json)
    return values, selection["cv_idx"], selection["vce_idx"], Path(ns.output), Path(ns.selection_json).resolve()


def build_source(values: dict[str, str], cv_idx: int, vce_idx: int, scripts_dir: Path, source_path: Path) -> str:
    payload = json.dumps(values, ensure_ascii=False, indent=2)
    scripts_dir_text = str(scripts_dir)
    source_path_text = str(source_path)
    return f'''"""Generated Starlane Python regression final-stage script."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path({scripts_dir_text!r})
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from final_regression import run_final


ARGS = {payload}
CV_IDX = {cv_idx}
VCE_IDX = {vce_idx}


def main() -> int:
    outputs = run_final(ARGS, cv_idx=CV_IDX, vce_idx=VCE_IDX, source_path={source_path_text!r})
    print(f"STARLANE_FINAL_OUTPUT: {{outputs['docx']}}")
    print(f"STARLANE_SOURCE_ARTIFACT: {{outputs['source']}}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def main() -> int:
    try:
        values, cv_idx, vce_idx, output, _selection = parse_args(sys.argv)
        output.parent.mkdir(parents=True, exist_ok=True)
        scripts_dir = Path(__file__).resolve().parent
        source = build_source(values, cv_idx, vce_idx, scripts_dir, output.resolve())
        output.write_text(source, encoding="utf-8")
        output.chmod(0o755)
        print(f"Generated: {output}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
