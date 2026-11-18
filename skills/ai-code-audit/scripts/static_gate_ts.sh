#!/usr/bin/env bash
# Non-mutating TypeScript gate: tsc --noEmit, eslint. Each tool optional.
set -euo pipefail
ORIG="$(pwd)"
cd "$(dirname "$0")/.."
ROOT="${AUDIT_ROOT:-$ORIG}"

TSC=""
if [ -x "$ROOT/node_modules/.bin/tsc" ]; then TSC="$ROOT/node_modules/.bin/tsc"
elif command -v tsc >/dev/null; then TSC="tsc"; fi
if [ -n "$TSC" ] && [ -f "$ROOT/tsconfig.json" ]; then
  echo "== tsc --noEmit =="
  (cd "$ROOT" && "$TSC" --noEmit --pretty false 2>&1 | head -40 || true)
else
  echo "skipped: tsc (no tsconfig.json or no local tsc)"
fi

ESLINT=""
if [ -x "$ROOT/node_modules/.bin/eslint" ]; then ESLINT="$ROOT/node_modules/.bin/eslint"
elif command -v eslint >/dev/null; then ESLINT="eslint"; fi
if [ -n "$ESLINT" ]; then
  echo
  echo "== eslint =="
  (cd "$ROOT" && "$ESLINT" --no-eslintrc --no-fix --format unix . 2>&1 | head -40 || true)
else
  echo
  echo "skipped: eslint (not installed)"
fi
