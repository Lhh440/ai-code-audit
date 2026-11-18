#!/usr/bin/env bash
# AI-slop rules. Uses ast-grep when installed, else the stdlib AST fallback.
set -euo pipefail
ORIG="$(pwd)"
cd "$(dirname "$0")/.."
export AUDIT_ROOT="${AUDIT_ROOT:-$ORIG}"
ARGS=()
for a in "$@"; do case "$a" in /*) ARGS+=("$a") ;; *) ARGS+=("$AUDIT_ROOT/$a") ;; esac; done

if command -v ast-grep >/dev/null; then
  ROOT="${AUDIT_ROOT:-$(pwd)}"
  echo "== ast-grep (rules/ai-slop.yml) =="
  ast-grep scan --config rules/ai-slop.yml "$ROOT" || true
  echo
  echo "note: ast-grep covers shape rules; the AST fallback covers semantics. Run both if unsure."
  exit 0
fi

echo "skipped: ast-grep (not installed) — using stdlib AST fallback"
exec python3 scripts/slop_scan.py "${ARGS[@]}"
