#!/usr/bin/env bash
# Non-mutating static gate: syntax, ruff, mypy. Each tool optional.
set -euo pipefail
ORIG="$(pwd)"
cd "$(dirname "$0")/.."
ROOT="${AUDIT_ROOT:-$ORIG}"
FILES="${AUDIT_FILES:-}"
for a in "$@"; do [ -f "$a" ] && FILES+="$a"$'\n'; done
if [ -n "$FILES" ]; then mapfile -t TARGETS <<<"$FILES"; else mapfile -t TARGETS < <(cd "$ROOT" && find . -name '*.py' -not -path '*/.*' | sed 's|^\./||'); fi
[ "${#TARGETS[@]}" -eq 0 ] && { echo "skipped: static_gate (no Python files)"; exit 0; }

echo "== py_compile =="
python3 -m py_compile "${TARGETS[@]}" && echo "ok" || echo "SYNTAX ERRORS above"

if command -v ruff >/dev/null; then
  echo
  echo "== ruff (read-only) =="
  (cd "$ROOT" && ruff check --output-format concise --select E,F,B,SIM,ASYNC,RUF "${TARGETS[@]}" || true)
else
  echo
  echo "skipped: ruff (not installed)"
fi

if command -v mypy >/dev/null; then
  echo
  echo "== mypy (no cache write) =="
  (cd "$ROOT" && mypy --cache-dir=/tmp/audit-mypy --no-error-summary "${TARGETS[@]}" 2>&1 | head -40 || true)
else
  echo
  echo "skipped: mypy (not installed)"
fi

find . -name '__pycache__' -newer package.json -maxdepth 1 >/dev/null 2>&1 || true
