#!/usr/bin/env bash
# Non-mutating Rust gate: cargo fmt --check, cargo check.
set -euo pipefail
ORIG="$(pwd)"
cd "$(dirname "$0")/.."
ROOT="${AUDIT_ROOT:-$ORIG}"

USAGE='Rust static gate: cargo fmt --check, then cargo check.

usage: static_gate_rust.sh [-h]

Environment: AUDIT_ROOT selects the crate (default: the directory the wrapper
was run in).

Reads: Cargo.toml and src/.
Writes: target/ via cargo check. This is the one gate that is not read-only.
Costs: cargo check compiles the crate graph; first run can fetch crates.
Exit: 0 even with findings; skipped tools are printed as `skipped:`.'
for a in "$@"; do case "$a" in -h|--help) printf '%s\n' "$USAGE"; exit 0 ;; esac; done

if ! command -v cargo >/dev/null; then echo "skipped: cargo toolchain (not installed)"; exit 0; fi
echo "== cargo fmt --check =="
(cd "$ROOT" && cargo fmt --check 2>&1 | head -30) || true
echo
echo "== cargo check (writes target/) =="
(cd "$ROOT" && cargo check --message-format short 2>&1 | head -40) || true
