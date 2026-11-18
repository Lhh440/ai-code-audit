#!/usr/bin/env bash
# Go slop rules. ast-grep when installed, regex fallback otherwise.
set -euo pipefail
ORIG="$(pwd)"
cd "$(dirname "$0")/.."
export AUDIT_ROOT="${AUDIT_ROOT:-$ORIG}"
ARGS=()
for a in "$@"; do case "$a" in -*) ARGS+=("$a") ;; /*) ARGS+=("$a") ;; *) ARGS+=("$AUDIT_ROOT/$a") ;; esac; done
for a in "$@"; do case "$a" in -h|--help) exec python3 "scripts/slop_scan_rust.py" --help ;; esac; done

if command -v ast-grep >/dev/null; then
  echo "== ast-grep (rules/ai-slop-rust.yml) =="
  ast-grep scan --config rules/ai-slop-rust.yml "$AUDIT_ROOT" || true
  exit 0
fi
echo "skipped: ast-grep (not installed) — using regex fallback"
exec python3 scripts/slop_scan_rust.py "${ARGS[@]}"
