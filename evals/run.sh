#!/usr/bin/env bash
# Eval harness. Recall on planted defects, and — more important — false positives
# on fixtures that are odd but correct.
#
# Usage: evals/run.sh [-v]
set -euo pipefail
cd "$(dirname "$0")/.."
SKILL="skills/ai-code-audit"
VERBOSE="${1:-}"
PASS=0
FAIL=0

lang_of() {
  local dir="$1"
  if find "$dir" -name '*.go' -print -quit | grep -q .; then echo go
  elif [ -f "$dir/Cargo.toml" ]; then echo rust
  elif find "$dir" -name '*.ts' -print -quit | grep -q .; then echo ts
  else echo py; fi
}

run_fixture() {
  local dir="$1"
  local lang
  lang="$(lang_of "evals/fixtures/$dir")"
  local out
  out="$(
    export AUDIT_ROOT="$PWD/evals/fixtures/$dir"
    case "$lang" in
      go)   { "$SKILL/scripts/check_imports_go.sh"; "$SKILL/scripts/probe_api_go.sh"; "$SKILL/scripts/slop_scan_go.sh"; } 2>/dev/null ;;
      rust) { "$SKILL/scripts/check_imports_rust.sh"; "$SKILL/scripts/probe_api_rust.sh"; "$SKILL/scripts/slop_scan_rust.sh"; } 2>/dev/null ;;
      ts) { "$SKILL/scripts/check_imports_ts.sh"; "$SKILL/scripts/probe_api_ts.sh"; "$SKILL/scripts/slop_scan_ts.sh"; } 2>/dev/null ;;
      *)  { "$SKILL/scripts/check_imports.sh"; "$SKILL/scripts/probe_api.sh"; "$SKILL/scripts/slop_scan.sh"; } 2>/dev/null ;;
    esac
  )"

  local missing=0 rule
  while read -r rule; do
    [ -z "$rule" ] && continue
    if ! printf '%s\n' "$out" | grep -q "\"rule\": \"$rule\""; then
      echo "  MISS  $dir: expected rule '$rule'"
      missing=$((missing + 1))
    fi
  done < "evals/fixtures/$dir/expect.txt"

  local blockers
  blockers="$(printf '%s\n' "$out" | grep -c '"severity": "BLOCKER"' || true)"
  case "$dir" in
    clean-*)
      if [ "$blockers" -gt 0 ]; then
        echo "  FP    $dir: $blockers blocker(s) on clean code"
        missing=$((missing + 1))
      fi
      ;;
  esac

  if [ "$VERBOSE" = "-v" ]; then printf '%s\n' "$out" | sed 's/^/    /'; fi

  if [ "$missing" -eq 0 ]; then
    echo "  ok    $dir ($lang)"
    PASS=$((PASS + 1))
  else
    echo "  FAIL  $dir ($lang)"
    FAIL=$((FAIL + 1))
  fi
}

for dir in evals/fixtures/*/; do
  run_fixture "$(basename "$dir")"
done

echo
echo "fixtures passed: $PASS  failed: $FAIL"
[ "$FAIL" -eq 0 ]
