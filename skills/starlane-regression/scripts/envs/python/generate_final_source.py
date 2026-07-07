"""Generate a runnable Python final-stage source file."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def parse_args(argv: list[str]) -> tuple[list[str], Path]:
    if len(argv) < 2:
        raise ValueError("Usage: generate_final_source.py <args_json_or_20_positional> [output_path]")
    first = argv[1]
    if first.strip().startswith("["):
        values = json.loads(first)
        output = Path(argv[2]) if len(argv) > 2 else Path.cwd() / "regression_generated.py"
    else:
        values = argv[1:22]
        output = Path(argv[22]) if len(argv) > 22 else Path.cwd() / "regression_generated.py"
    if len(values) < 20:
        raise ValueError(f"Expected 20 args: 18 summary args + cv_idx + vce_idx, got {len(values)}")
    return [str(v) for v in values], output


def build_source(values: list[str], scripts_dir: Path, source_path: Path) -> str:
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

from final import run_final


ARGS = {payload}


def main() -> int:
    outputs = run_final(ARGS, source_path={source_path_text!r})
    print(f"STARLANE_FINAL_OUTPUT: {{outputs['docx']}}")
    print(f"STARLANE_SOURCE_ARTIFACT: {{outputs['source']}}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def main() -> int:
    try:
        values, output = parse_args(sys.argv)
        output.parent.mkdir(parents=True, exist_ok=True)
        scripts_dir = Path(__file__).resolve().parent
        source = build_source(values, scripts_dir, output.resolve())
        output.write_text(source, encoding="utf-8")
        output.chmod(0o755)
        print(f"Generated: {output}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
