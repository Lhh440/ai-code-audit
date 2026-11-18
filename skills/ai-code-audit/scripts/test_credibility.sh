#!/usr/bin/env bash
# Test credibility: does the suite still fail when the implementation is reverted?
#
# Part 1 (safe): pattern scan of the test diff for weakened assertions.
# Part 2 (touches the worktree): stash changed non-test files, run the changed
#         tests, restore. Tests that pass with the implementation gone prove
#         nothing about this change.
#
# Usage: test_credibility.sh [base-ref] [--no-revert]
set -euo pipefail
ORIG="$(pwd)"
cd "$(dirname "$0")/.."
ROOT="${AUDIT_ROOT:-$(git -C "$ORIG" rev-parse --show-toplevel 2>/dev/null || echo "$ORIG")}"
BASE="${1:-${AUDIT_BASE:-}}"
REVERT=1
for arg in "$@"; do [ "$arg" = "--no-revert" ] && REVERT=0; done
[ "$BASE" = "--no-revert" ] && BASE="${AUDIT_BASE:-}"

command -v git >/dev/null || { echo "skipped: test_credibility (no git)"; exit 0; }
git -C "$ROOT" rev-parse --git-dir >/dev/null 2>&1 || { echo "skipped: test_credibility (not a repo)"; exit 0; }
[ -n "$BASE" ] || { echo "skipped: test_credibility (no base ref; pass one)"; exit 0; }

mapfile -t TEST_FILES < <(git -C "$ROOT" diff --name-only "$BASE"... 2>/dev/null | grep -E '(^|/)(test_[^/]*|tests?/[^/]*)\.py$|conftest\.py$' || true)
mapfile -t SRC_FILES < <(git -C "$ROOT" diff --name-only "$BASE"... 2>/dev/null | grep -E '\.py$' | grep -vE '(^|/)(test_[^/]*|tests?/)|conftest\.py$' || true)

echo "== weakened-assertion scan =="
if [ "${#TEST_FILES[@]}" -eq 0 ]; then
  echo "no test files in this diff — every behaviour change is unverified by definition"
else
  echo "changed test files: ${#TEST_FILES[@]}"
  DIFF="$(git -C "$ROOT" diff "$BASE"... -- "${TEST_FILES[@]}" 2>/dev/null || true)"
  check() {
    local label="$1" pattern="$2" note="$3"
    local hits
    hits="$(printf '%s\n' "$DIFF" | grep -E "$pattern" | head -12 || true)"
    if [ -n "$hits" ]; then
      echo
      echo "! $label — $note"
      printf '%s\n' "$hits" | sed 's/^/    /'
    fi
  }
  check "removed assertions" '^-[[:space:]]*(self\.)?assert' "deleted asserts lower coverage"
  check "added skips" '^\+.*(pytest\.mark\.(skip|xfail)|@skip|skipIf|unittest\.skip)' "skipped tests do not run in CI"
  check "focus markers" '^\+.*(\.only|focus)' "only-markers silently disable the rest"
  check "loosened comparisons" '^-.*assert(Equal|In|AlmostEqual)\(.*\)[[:space:]]*$' "check the replacement is not weaker"
  check "tautological asserts" '^\+.*assert(True| 1)([[:space:]]|$)' "always green"
  check "generic raises" '^\+.*raises\((Exception|BaseException)\)' "any failure satisfies it, including a typo"
  check "mocked subject" '^\+.*patch\(.*(self|subject|under_test)' "patching the unit under test tests the mock"
  check "snapshot overwrite" '^\+.*(snapshot_update|--snapshot-update|assert_match)' "regenerated snapshots accept any output"
fi

[ "$REVERT" = 1 ] || { echo; echo "revert-check skipped (--no-revert)"; exit 0; }
if [ "${#SRC_FILES[@]}" -eq 0 ] || [ "${#TEST_FILES[@]}" -eq 0 ]; then
  echo; echo "== revert-check =="; echo "skipped: need at least one source and one test file"
  exit 0
fi
if ! command -v pytest >/dev/null; then
  echo; echo "== revert-check =="; echo "skipped: pytest not installed"
  exit 0
fi
if ! git -C "$ROOT" diff --quiet HEAD -- 2>/dev/null; then :; fi

echo
echo "== revert-check =="
echo "stashing ${#SRC_FILES[@]} source file(s), keeping tests; then running the changed tests"
if ! git -C "$ROOT" stash push --quiet -m "ai-code-audit revert-check" -- "${SRC_FILES[@]}"; then
  echo "stash failed (dirty index?); run the check manually"; exit 0
fi
restore() { git -C "$ROOT" stash pop --quiet || echo "!! stash pop failed — run 'git stash list' and restore by hand"; }
trap restore EXIT

set +e
OUT="$(cd "$ROOT" && pytest "${TEST_FILES[@]}" -q --no-header -p no:cacheprovider 2>&1)"
STATUS=$?
set -e
printf '%s\n' "$OUT" | tail -15

if [ "$STATUS" -eq 0 ]; then
  echo
  echo "! every changed test still passes WITHOUT the implementation."
  echo "  These assertions do not pin the new behaviour; treat the green suite as no evidence."
else
  echo
  echo "ok: the suite fails with the implementation reverted, so it exercises the change."
fi
