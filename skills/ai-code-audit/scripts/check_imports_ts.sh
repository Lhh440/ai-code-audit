#!/usr/bin/env bash
# TypeScript variant. See check_imports_ts.py for the rules.
set -euo pipefail
ORIG="$(pwd)"
cd "$(dirname "$0")/.."
export AUDIT_ROOT="${AUDIT_ROOT:-$ORIG}"
ARGS=()
for a in "$@"; do case "$a" in -*) ARGS+=("$a") ;; /*) ARGS+=("$a") ;; *) ARGS+=("$AUDIT_ROOT/$a") ;; esac; done
command -v python3 >/dev/null || { echo "skipped: check_imports_ts (no python3)"; exit 0; }
exec python3 scripts/check_imports_ts.py "${ARGS[@]}"
