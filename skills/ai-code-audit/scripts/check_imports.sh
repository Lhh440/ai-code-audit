#!/usr/bin/env bash
# Unresolvable imports and undeclared dependencies.
set -euo pipefail
ORIG="$(pwd)"
cd "$(dirname "$0")/.."
export AUDIT_ROOT="${AUDIT_ROOT:-$ORIG}"
ARGS=()
for a in "$@"; do case "$a" in -*) ARGS+=("$a") ;; /*) ARGS+=("$a") ;; *) ARGS+=("$AUDIT_ROOT/$a") ;; esac; done
command -v python3 >/dev/null || { echo "skipped: check_imports (no python3)"; exit 0; }
exec python3 scripts/check_imports.py "${ARGS[@]}"
