#!/usr/bin/env bash
# Non-mutating static gate: syntax, ruff, mypy. Each tool optional.
set -euo pipefail
ORIG="$(pwd)"
cd "$(dirname "$0")/.."
ROOT="${AUDIT_ROOT:-$ORIG}"

USAGE='Python static gate: py_compile, then ruff and mypy when installed.

usage: static_gate.sh [-h] [paths...]

Without paths, checks every .py file under $AUDIT_ROOT (default: the directory
the wrapper was run in). Relative paths are resolved against that directory.

Reads: .py files.
Writes: __pycache__/ next to compiled files; mypy cache under /tmp.
Costs: syntax check is cheap; ruff/mypy can be slow on large trees.
Exit: 0 even with findings; findings go to stdout.'

for a in "$@"; do case "$a" in -h|--help) printf '%s\n' "$USAGE"; exit 0 ;; esac; done

FILES="${AUDIT_FILES:-}"
for a in "$@"; do
  case "$a" in -*) continue ;; esac
  case "$a" in /*) [ -f "$a" ] && FILES+="$a"$'\n' ;; *) [ -f "$ROOT/$a" ] && FILES+="$ROOT/$a"$'\n' ;; esac
done
if [ -n "$FILES" ]; then mapfile -t TARGETS <<<"${FILES%$'\n'}"; else mapfile -t TARGETS < <(cd "$ROOT" && find . -name '*.py' -not -path '*/.*' | sed 's|^\./||'); fi
[ "${#TARGETS[@]}" -eq 0 ] && { echo "skipped: static_gate (no Python files)"; exit 0; }

command -v python3 >/dev/null || { echo "skipped: static_gate (no python3)"; exit 0; }
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
