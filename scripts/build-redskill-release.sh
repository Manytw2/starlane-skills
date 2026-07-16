#!/usr/bin/env sh
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SKILL_NAME="starlane-regression"
SKILL_DIR="$ROOT/skills/$SKILL_NAME"
RELEASE_DIR="$ROOT/release/redskill"
REDSKILL_README="$RELEASE_DIR/README.md"

usage() {
  cat <<'EOF'
Usage:
  scripts/build-redskill-release.sh VERSION

Build the Red Skill upload zip for starlane-regression.

Example:
  scripts/build-redskill-release.sh v1.0.0
EOF
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi

if [ "$#" -ne 1 ]; then
  echo "VERSION is required." >&2
  usage >&2
  exit 2
fi

VERSION="$1"
case "$VERSION" in
  v[0-9]*.[0-9]*.[0-9]*)
    ;;
  *)
    echo "VERSION must look like v1.0.0" >&2
    exit 2
    ;;
esac

ZIP_PATH="$RELEASE_DIR/$SKILL_NAME-redskill-$VERSION.zip"

if [ ! -f "$SKILL_DIR/SKILL.md" ]; then
  echo "Missing skill entry: ${SKILL_DIR#$ROOT/}/SKILL.md" >&2
  exit 1
fi

if [ ! -d "$SKILL_DIR/references" ]; then
  echo "Missing expected skill references under ${SKILL_DIR#$ROOT/}" >&2
  exit 1
fi

if [ ! -f "$REDSKILL_README" ]; then
  echo "Missing Red Skill package README: ${REDSKILL_README#$ROOT/}" >&2
  exit 1
fi

tmp_root="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp_root"
}
trap cleanup EXIT INT TERM

package_dir="$tmp_root/$SKILL_NAME"
mkdir -p "$package_dir"

cp "$SKILL_DIR/SKILL.md" "$package_dir/"
cp "$REDSKILL_README" "$package_dir/README.md"
cp -R "$SKILL_DIR/references" "$package_dir/"

find "$package_dir" -name '.DS_Store' -type f -delete
find "$package_dir" -name '__pycache__' -type d -prune -exec rm -rf {} +
find "$package_dir" -name '*.pyc' -type f -delete

mkdir -p "$RELEASE_DIR"
rm -f "$ZIP_PATH"

(
  cd "$tmp_root"
  zip -qr "$ZIP_PATH" "$SKILL_NAME"
)

zip_size_bytes="$(wc -c < "$ZIP_PATH" | tr -d ' ')"
zip_size_mb="$(awk "BEGIN {printf \"%.2f\", $zip_size_bytes / 1024 / 1024}")"
file_count="$(zipinfo -1 "$ZIP_PATH" | wc -l | tr -d ' ')"

if [ "$zip_size_bytes" -gt 31457280 ]; then
  echo "Release zip exceeds Red Skill 30MB total limit: ${zip_size_mb}MB" >&2
  exit 1
fi

if ! zipinfo -1 "$ZIP_PATH" | grep -qx "$SKILL_NAME/SKILL.md"; then
  echo "Release zip is missing $SKILL_NAME/SKILL.md" >&2
  exit 1
fi

if ! zipinfo -1 "$ZIP_PATH" | grep -qx "$SKILL_NAME/README.md"; then
  echo "Release zip is missing $SKILL_NAME/README.md" >&2
  exit 1
fi

if zipinfo -1 "$ZIP_PATH" | grep -Eq '(^|/)(scripts/|pyproject\.toml$|uv\.lock$|.*\.do$)'; then
  echo "Release zip includes files filtered by Red SkillHub; keep this package to docs only." >&2
  exit 1
fi

printf 'Built Red Skill release: %s\n' "${ZIP_PATH#$ROOT/}"
printf 'Files: %s\n' "$file_count"
printf 'Size: %sMB\n' "$zip_size_mb"
