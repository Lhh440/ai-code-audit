#!/usr/bin/env bash
# Non-mutating Go gate: gofmt -l, go vet.
set -euo pipefail
ORIG="$(pwd)"
cd "$(dirname "$0")/.."
ROOT="${AUDIT_ROOT:-$ORIG}"
if ! command -v go >/dev/null; then echo "skipped: go toolchain (not installed)"; exit 0; fi
echo "== gofmt -l =="
(cd "$ROOT" && gofmt -l . 2>&1 | head -30) || true
echo
echo "== go vet =="
(cd "$ROOT" && go vet ./... 2>&1 | head -40) || true
