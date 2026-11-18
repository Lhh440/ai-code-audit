#!/usr/bin/env bash
# Smoke-test test_credibility.sh across all four languages with fake runners.
# The fake runner's exit code is controlled by a marker file, so this checks
# classification, the revert, the verdict wording, and worktree restoration —
# not the real test frameworks.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"
SKILL="$ROOT_DIR/skills/ai-code-audit/scripts/test_credibility.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
PASS=0
FAIL=0

fake() {  # fake <path>; exits 0 when .weak exists, 1 otherwise
  mkdir -p "$(dirname "$1")"
  cat >"$1" <<'EOF'
#!/usr/bin/env bash
[ -f .weak ] && exit 0
exit 1
EOF
  chmod +x "$1"
}

new_repo() {
  mkdir -p "$TMP/$1"
  git -C "$TMP/$1" init -q
  git -C "$TMP/$1" config user.email a@b.c
  git -C "$TMP/$1" config user.name test
  printf '.weak\n' >"$TMP/$1/.gitignore"
}

base_commit() {  # base_commit <dir>
  git -C "$TMP/$1" add -A
  git -C "$TMP/$1" commit -qm base
}

change_commit() {  # change_commit <dir> <weak|strong> <impl-file> <base> <change> <test-file> <test>
  local dir="$1" mode="$2" file="$3" initial="$4" changed="$5" test_file="$6" test="$7"
  printf '%s\n' "$initial" >"$TMP/$dir/$file"
  base_commit "$dir"
  mkdir -p "$(dirname "$TMP/$dir/$test_file")"
  printf '%s\n' "$changed" >"$TMP/$dir/$file"
  printf '%s\n' "$test" >"$TMP/$dir/$test_file"
  git -C "$TMP/$dir" add -A
  git -C "$TMP/$dir" commit -qm change
  if [ "$mode" = weak ]; then touch "$TMP/$dir/.weak"; else rm -f "$TMP/$dir/.weak"; fi
}

run_case() {  # run_case <name> <dir> <expected phrase>
  local name="$1" dir="$2" expected="$3" out
  out="$(cd "$TMP/$dir" && PATH="$TMP/bin:$PATH" AUDIT_ROOT="$TMP/$dir" "$SKILL" HEAD~1 2>&1)" || true
  if printf '%s\n' "$out" | grep -q "$expected"; then
    echo "  ok    $name"
    PASS=$((PASS + 1))
  else
    echo "  FAIL  $name (missing: $expected)"
    printf '%s\n' "$out" | tail -6 | sed 's/^/    /'
    FAIL=$((FAIL + 1))
  fi
  if [ -n "$(git -C "$TMP/$dir" status --porcelain)" ]; then
    echo "  FAIL  $name (worktree not restored)"
    FAIL=$((FAIL + 1))
  fi
  if [ -n "$(git -C "$TMP/$dir" stash list)" ]; then
    echo "  FAIL  $name (stash left behind)"
    FAIL=$((FAIL + 1))
  fi
}

mkdir -p "$TMP/bin"

# Python: weak then strong.
new_repo pyweak
fake "$TMP/bin/pytest"
change_commit pyweak weak impl.py 'def f(): return 1' 'def f(): return 2' test_impl.py 'def test_f(): assert f() in (1, 2)'
run_case "python weak" pyweak "still passes WITHOUT the implementation"

new_repo pystrong
change_commit pystrong strong impl.py 'def f(): return 1' 'def f(): return 2' test_impl.py 'def test_f(): assert f() == 2'
run_case "python strong" pystrong "suite fails with the implementation reverted"

# TypeScript: local vitest.
new_repo ts
mkdir -p "$TMP/ts/src"
fake "$TMP/ts/node_modules/.bin/vitest"
printf '{"scripts":{"test":"vitest"}}\n' >"$TMP/ts/package.json"
change_commit ts weak src/impl.ts 'export const f = 1' 'export const f = 2' src/impl.test.ts 'import { f } from "./impl";'
run_case "typescript weak" ts "still passes WITHOUT the implementation"

# Go.
new_repo go
fake "$TMP/bin/go"
printf 'module example.com/x\n' >"$TMP/go/go.mod"
change_commit go strong impl.go 'package x' 'package x // changed' impl_test.go 'package x'
run_case "go strong" go "suite fails with the implementation reverted"

# Rust integration test.
new_repo rust
fake "$TMP/bin/cargo"
mkdir -p "$TMP/rust/src" "$TMP/rust/tests"
printf '[package]\nname = "x"\nversion = "0.1.0"\nedition = "2021"\n' >"$TMP/rust/Cargo.toml"
change_commit rust strong src/lib.rs 'pub fn f() -> u8 { 1 }' 'pub fn f() -> u8 { 2 }' tests/it.rs '#[test] fn it_works() { assert_eq!(x::f(), 2); }'
run_case "rust strong" rust "suite fails with the implementation reverted"

echo
echo "credibility cases passed: $PASS  failed: $FAIL"
[ "$FAIL" -eq 0 ]
