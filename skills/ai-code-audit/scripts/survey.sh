#!/usr/bin/env bash
# Rank changed files by review risk. Read-only.
# Usage: survey.sh [base-ref]
set -euo pipefail
ORIG="$(pwd)"
cd "$(dirname "$0")/.."

USAGE='Rank changed files by review risk. Read-only.

usage: survey.sh [-h] [base-ref]

base-ref defaults to origin/main, origin/master, main, master or HEAD~1.
Without git history it lists the tree instead.

Reads: git history, changed file names and sizes.
Writes: a file list under /tmp (path printed at the end).
Exit: 0 even when there is nothing to rank.'
for a in "$@"; do case "$a" in -h|--help) printf '%s\n' "$USAGE"; exit 0 ;; esac; done
ROOT="${AUDIT_ROOT:-$(git -C "$ORIG" rev-parse --show-toplevel 2>/dev/null || echo "$ORIG")}"
export AUDIT_ROOT="$ROOT"

BASE="${1:-${AUDIT_BASE:-}}"
HAVE_GIT=0
if command -v git >/dev/null && git -C "$ROOT" rev-parse --git-dir >/dev/null 2>&1; then
  HAVE_GIT=1
fi
if [ -z "$BASE" ] && [ "$HAVE_GIT" = 1 ]; then
  for candidate in origin/main origin/master main master HEAD~1; do
    if git -C "$ROOT" rev-parse --verify --quiet "$candidate" >/dev/null; then BASE="$candidate"; break; fi
  done
fi

echo "== scope =="
echo "root: $ROOT"
echo "base: ${BASE:-<none, surveying working tree>}"
echo

if [ "$HAVE_GIT" = 1 ] && [ -n "$BASE" ]; then
  echo "== diff stat =="
  git -C "$ROOT" diff --numstat "$BASE"... 2>/dev/null || git -C "$ROOT" diff --numstat "$BASE" || true
  echo
  CHANGED="$(git -C "$ROOT" diff --name-only "$BASE"... 2>/dev/null || git -C "$ROOT" diff --name-only "$BASE" || true)"
else
  echo "== diff stat =="
  echo "(no git history; using full tree)"
  CHANGED="$(cd "$ROOT" && find . -name '*.py' -not -path '*/.*' | sed 's|^\./||' | head -200)"
fi

echo "== changed files, risk order =="
printf '%s\n' "$CHANGED" | awk 'NF' | while read -r f; do
  [ -f "$ROOT/$f" ] || continue
  lines=$(wc -l <"$ROOT/$f" 2>/dev/null || echo 0)
  score=0
  case "$f" in
    *.lock|*.min.*|*/migrations/*) score=$((score - 6)) ;;
    tests/*|*/tests/*|test_*.py|*_test.py) score=$((score - 3)) ;;
  esac
  case "$f" in
    *auth*|*crypto*|*secret*|*payment*|*billing*|*perm*) score=$((score + 5)) ;;
  esac
  case "$f" in
    *schema*|*migrat*|*config*|*settings*|*/api/*|*route*) score=$((score + 3)) ;;
  esac
  if [ "$lines" -gt 400 ]; then score=$((score + 2)); fi
  printf '%+d\t%s\t%s\n' "$score" "$lines" "$f"
done | sort -rn -k1
echo
echo "== generated / vendored (skim only) =="
printf '%s\n' "$CHANGED" | grep -E '\.lock$|\.min\.|migrations/|node_modules/|\.venv/' || echo "(none)"
echo
awk 'NF' <<<"$CHANGED" >/dev/null 2>&1 || true
{
  printf '%s\n' "$CHANGED" | awk 'NF'
} >/tmp/audit_files.$$ 2>/dev/null || true
echo "file list written to /tmp/audit_files.$$ (export AUDIT_FILES=\$(cat /tmp/audit_files.$$) for later steps)"
