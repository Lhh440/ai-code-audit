#!/usr/bin/env bash
# Hallucinated symbols and unsupported keyword arguments.
set -euo pipefail
ORIG="$(pwd)"
cd "$(dirname "$0")/.."
export AUDIT_ROOT="${AUDIT_ROOT:-$ORIG}"
ARGS=()
for a in "$@"; do case "$a" in -*) ARGS+=("$a") ;; /*) ARGS+=("$a") ;; *) ARGS+=("$AUDIT_ROOT/$a") ;; esac; done
command -v python3 >/dev/null || { echo "skipped: probe_api (no python3)"; exit 0; }
exec python3 scripts/probe_api.py "${ARGS[@]}"
