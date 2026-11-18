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

USAGE='Credibility check for the tests in a diff.

usage: test_credibility.sh [-h] [base-ref] [--no-revert]

base-ref defaults to $AUDIT_BASE. The revert-check needs git and a clean enough
tree; it stashes changed implementation files, keeps the tests, runs them, then
restores the implementation.

Reads: the diff, test files, and the test runner.
Writes: the git worktree via `git stash push` / `git stash pop`.
Costs: one test-run per detected language; may touch network or a database if
       the tests do.
Exit: 0 even when tests are weak; `--no-revert` keeps the scan read-only.'

for a in "$@"; do case "$a" in -h|--help) printf '%s\n' "$USAGE"; exit 0 ;; esac; done

ROOT="${AUDIT_ROOT:-$(git -C "$ORIG" rev-parse --show-toplevel 2>/dev/null || echo "$ORIG")}"
BASE=""
REVERT=1
for arg in "$@"; do
  case "$arg" in
    --no-revert) REVERT=0 ;;
    -*) ;;
    *) BASE="$arg" ;;
  esac
done
BASE="${BASE:-${AUDIT_BASE:-}}"

command -v git >/dev/null || { echo "skipped: test_credibility (no git)"; exit 0; }
git -C "$ROOT" rev-parse --git-dir >/dev/null 2>&1 || { echo "skipped: test_credibility (not a repo)"; exit 0; }
[ -n "$BASE" ] || { echo "skipped: test_credibility (no base ref; pass one)"; exit 0; }

DIFF_FILES="$(git -C "$ROOT" diff --name-only "$BASE"... 2>/dev/null || true)"
PY_TESTS=(); PY_SRC=()
TS_TESTS=(); TS_SRC=()
GO_TESTS=(); GO_SRC=()
RS_TESTS=(); RS_SRC=()

while IFS= read -r f; do
  [ -n "$f" ] || continue
  case "$f" in
    *.py)
      case "$f" in
        test_*.py|*_test.py|tests.py|test.py|conftest.py|tests/*|test/*|*/tests/*|*/test/*)
          PY_TESTS+=("$f") ;;
        *) PY_SRC+=("$f") ;;
      esac ;;
    *.ts|*.tsx|*.js|*.jsx)
      case "$f" in
        *.test.ts|*.spec.ts|*.test.tsx|*.spec.tsx|*.test.js|*.spec.js|__tests__/*|*/__tests__/*)
          TS_TESTS+=("$f") ;;
        *) TS_SRC+=("$f") ;;
      esac ;;
    *_test.go) GO_TESTS+=("$f") ;;
    *.go) GO_SRC+=("$f") ;;
    */tests/*.rs|tests/*.rs|tests.rs)
      RS_TESTS+=("$f") ;;
    *.rs) RS_SRC+=("$f") ;;
  esac
done <<<"$DIFF_FILES"

ALL_TESTS=("${PY_TESTS[@]}" "${TS_TESTS[@]}" "${GO_TESTS[@]}" "${RS_TESTS[@]}")

echo "== weakened-assertion scan =="
if [ "${#ALL_TESTS[@]}" -eq 0 ]; then
  echo "no test files in this diff — every behaviour change is unverified by definition"
else
  echo "changed test files: ${#ALL_TESTS[@]}"
  DIFF="$(git -C "$ROOT" diff "$BASE"... -- "${ALL_TESTS[@]}" 2>/dev/null || true)"
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
  check "removed assertions" '^-[[:space:]]*(self\.)?(assert|assert_eq!|assert_ne!|expect\(|t\.(Fatal|Error))' "deleted asserts lower coverage"
  check "added skips" '^\+.*(pytest\.mark\.(skip|xfail)|@skip|skipIf|unittest\.skip|\.skip\(|t\.Skip|#\[ignore\])' "skipped tests do not run in CI"
  check "focus markers" '^\+.*(\.only\(|fdescribe\(|fit\()' "only-markers silently disable the rest"
  check "loosened comparisons" '^-.*assert(Equal|In|AlmostEqual)\(.*\)[[:space:]]*$' "check the replacement is not weaker"
  check "tautological asserts" '^\+.*(assert(True| 1)([[:space:]]|$)|expect\(true\)\.toBe\(true\))' "always green"
  check "self-comparison" '^\+.*assert_eq!\(([^,]+), *\1\)' "compares a value to itself"
  check "generic raises" '^\+.*(raises\((Exception|BaseException)\)|#\[should_panic\])' "any failure satisfies it, including a typo"
  check "mocked subject" '^\+.*patch\(.*(self|subject|under_test)' "patching the unit under test tests the mock"
  check "snapshot overwrite" '^\+.*(snapshot_update|--snapshot-update|assert_match)' "regenerated snapshots accept any output"
fi

[ "$REVERT" = 1 ] || { echo; echo "revert-check skipped (--no-revert)"; exit 0; }

REVERT_ACTIVE=0
RESTORE_STASH=0
RESTORE_FILES=()
restore() {
  [ "$REVERT_ACTIVE" = 1 ] || return 0
  local f
  for f in "${RESTORE_FILES[@]}"; do
    if git -C "$ROOT" cat-file -e "HEAD:$f" 2>/dev/null; then
      git -C "$ROOT" checkout HEAD -- "$f"
    else
      rm -f "$ROOT/$f"
    fi
  done
  if [ "$RESTORE_STASH" = 1 ]; then
    git -C "$ROOT" stash pop --quiet || echo "!! stash pop failed — run 'git stash list' and restore by hand"
  fi
  REVERT_ACTIVE=0
}
trap restore EXIT INT TERM

# run_revert <label> <runner-command> <test...> -- <source...>
run_revert() {
  local label="$1" runner="$2"
  shift 2
  local tests=() src=() after_sep=0
  for item in "$@"; do
    if [ "$item" = "--" ]; then after_sep=1; continue; fi
    if [ "$after_sep" = 1 ]; then src+=("$item"); else tests+=("$item"); fi
  done
  [ "${#tests[@]}" -gt 0 ] && [ "${#src[@]}" -gt 0 ] || return 0

  echo
  echo "== revert-check ($label) =="
  echo "reverting ${#src[@]} source file(s), keeping tests; then running the changed tests"

  RESTORE_FILES=("${src[@]}")
  REVERT_ACTIVE=1
  if [ -n "$(git -C "$ROOT" status --porcelain -- "${src[@]}" 2>/dev/null)" ]; then
    if ! git -C "$ROOT" stash push -u --quiet -m "ai-code-audit revert-check ($label)" -- "${src[@]}"; then
      echo "stash failed (dirty index?); run the check manually"
      REVERT_ACTIVE=0
      return 0
    fi
    RESTORE_STASH=1
  fi

  local base_tree f out status
  base_tree="$(git -C "$ROOT" merge-base HEAD "$BASE" 2>/dev/null || printf '%s' "$BASE")"
  for f in "${src[@]}"; do
    if git -C "$ROOT" cat-file -e "$base_tree:$f" 2>/dev/null; then
      git -C "$ROOT" checkout "$base_tree" -- "$f" 2>/dev/null || true
    else
      rm -f "$ROOT/$f"
    fi
  done

  set +e
  out="$(cd "$ROOT" && eval "$runner" 2>&1)"
  status=$?
  set -e
  printf '%s\n' "$out" | tail -15

  if [ "$status" -eq 0 ]; then
    echo
    echo "! every changed $label test still passes WITHOUT the implementation."
    echo "  These assertions do not pin the new behaviour; treat the green suite as no evidence."
  else
    echo
    echo "ok: the $label suite fails with the implementation reverted, so it exercises the change."
  fi
  restore
  RESTORE_STASH=0
  RESTORE_FILES=()
}

if [ "${#PY_TESTS[@]}" -gt 0 ] && [ "${#PY_SRC[@]}" -gt 0 ]; then
  if command -v pytest >/dev/null; then
    printf -v PY_CMD 'pytest %q ' "${PY_TESTS[@]}"
    PY_CMD+="-q --no-header -p no:cacheprovider"
    run_revert python "$PY_CMD" ${PY_TESTS[@]+"${PY_TESTS[@]}"} -- ${PY_SRC[@]+"${PY_SRC[@]}"}
  else
    echo; echo "== revert-check (python) =="; echo "skipped: pytest not installed"
  fi
fi

if [ "${#TS_TESTS[@]}" -gt 0 ] && [ "${#TS_SRC[@]}" -gt 0 ]; then
  TS_RUNNER=""
  if [ -x "$ROOT/node_modules/.bin/vitest" ]; then TS_RUNNER="$ROOT/node_modules/.bin/vitest run"
  elif [ -x "$ROOT/node_modules/.bin/jest" ]; then TS_RUNNER="$ROOT/node_modules/.bin/jest --runTestsByPath"
  elif command -v vitest >/dev/null; then TS_RUNNER="vitest run"
  elif command -v jest >/dev/null; then TS_RUNNER="jest --runTestsByPath"
  fi
  if [ -n "$TS_RUNNER" ]; then
    printf -v TS_CMD '%s %q ' "$TS_RUNNER" "${TS_TESTS[@]}"
    if [[ "$TS_RUNNER" == *jest* ]]; then TS_CMD+="--passWithNoTests"; else TS_CMD+="--reporter=basic"; fi
    run_revert typescript "$TS_CMD" ${TS_TESTS[@]+"${TS_TESTS[@]}"} -- ${TS_SRC[@]+"${TS_SRC[@]}"}
  else
    echo; echo "== revert-check (typescript) =="; echo "skipped: no local vitest or jest"
  fi
fi

if [ "${#GO_TESTS[@]}" -gt 0 ] && [ "${#GO_SRC[@]}" -gt 0 ]; then
  if command -v go >/dev/null; then
    GO_DIRS=()
    for f in "${GO_TESTS[@]}"; do
      d="./$(dirname "$f")"
      case " ${GO_DIRS[*]-} " in *" $d "*) ;; *) GO_DIRS+=("$d") ;; esac
    done
    run_revert go "go test ${GO_DIRS[*]}" ${GO_TESTS[@]+"${GO_TESTS[@]}"} -- ${GO_SRC[@]+"${GO_SRC[@]}"}
  else
    echo; echo "== revert-check (go) =="; echo "skipped: go toolchain not installed"
  fi
fi

if [ "${#RS_TESTS[@]}" -gt 0 ] && [ "${#RS_SRC[@]}" -gt 0 ]; then
  if command -v cargo >/dev/null; then
    RS_NAMES=""
    for f in "${RS_TESTS[@]}"; do
      stem="$(basename "$f" .rs)"
      RS_NAMES+=" --test $stem"
    done
    run_revert rust "cargo test$RS_NAMES" ${RS_TESTS[@]+"${RS_TESTS[@]}"} -- ${RS_SRC[@]+"${RS_SRC[@]}"}
  else
    echo; echo "== revert-check (rust) =="; echo "skipped: cargo toolchain not installed"
  fi
fi

if [ "${#ALL_TESTS[@]}" -eq 0 ]; then
  echo; echo "== revert-check =="; echo "skipped: no changed test files"
fi
