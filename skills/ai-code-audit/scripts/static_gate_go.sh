#!/usr/bin/env bash
# Non-mutating Go gate: gofmt -l, go vet.
set -euo pipefail
ORIG="$(pwd)"
cd "$(dirname "$0")/.."
ROOT="${AUDIT_ROOT:-$ORIG}"

USAGE='Go static gate: gofmt -l, then go vet.

usage: static_gate_go.sh [-h]

Environment: AUDIT_ROOT selects the tree (default: the directory the wrapper
was run in).

Reads: .go files and go.mod.
Writes: nothing (the module cache may be populated by the toolchain).
Costs: go vet compiles the package graph; first run can fetch modules.
Exit: 0 even with findings; skipped tools are printed as `skipped:`.'
for a in "$@"; do case "$a" in -h|--help) printf '%s\n' "$USAGE"; exit 0 ;; esac; done

if ! command -v go >/dev/null; then echo "skipped: go toolchain (not installed)"; exit 0; fi
echo "== gofmt -l =="
(cd "$ROOT" && gofmt -l . 2>&1 | head -30) || true
echo
echo "== go vet =="
(cd "$ROOT" && go vet ./... 2>&1 | head -40) || true
