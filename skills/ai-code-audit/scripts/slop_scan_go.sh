#!/usr/bin/env bash
# Go slop rules. ast-grep when installed, regex fallback otherwise.
set -euo pipefail
ORIG="$(pwd)"
cd "$(dirname "$0")/.."
export AUDIT_ROOT="${AUDIT_ROOT:-$ORIG}"
ARGS=()
for a in "$@"; do case "$a" in -*) ARGS+=("$a") ;; /*) ARGS+=("$a") ;; *) ARGS+=("$AUDIT_ROOT/$a") ;; esac; done
for a in "$@"; do case "$a" in -h|--help) exec python3 "scripts/slop_scan_go.py" --help ;; esac; done

if command -v ast-grep >/dev/null; then
  if [ "${#ARGS[@]}" -gt 0 ]; then TARGETS=("${ARGS[@]}"); else TARGETS=("$AUDIT_ROOT"); fi
  echo "== ast-grep (rules/ai-slop-go.yml) =="
  ast-grep scan --config rules/ai-slop-go.yml "${TARGETS[@]}" || true
  exit 0
fi
echo "skipped: ast-grep (not installed) — using regex fallback"
exec python3 scripts/slop_scan_go.py "${ARGS[@]}"
