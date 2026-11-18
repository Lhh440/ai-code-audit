#!/usr/bin/env bash
# Non-mutating Rust gate: cargo fmt --check, cargo check.
set -euo pipefail
ORIG="$(pwd)"
cd "$(dirname "$0")/.."
ROOT="${AUDIT_ROOT:-$ORIG}"
if ! command -v cargo >/dev/null; then echo "skipped: cargo toolchain (not installed)"; exit 0; fi
echo "== cargo fmt --check =="
(cd "$ROOT" && cargo fmt --check 2>&1 | head -30) || true
echo
echo "== cargo check (writes target/) =="
(cd "$ROOT" && cargo check --message-format short 2>&1 | head -40) || true
