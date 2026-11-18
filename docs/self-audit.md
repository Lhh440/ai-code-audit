# Self-audit

This package audited by itself, during development. Reports kept as written,
including the misses. The point is not a clean sheet — it is showing what the
probes catch when the code under review is real.

Base: the working tree, before first release. Reviewer: the author (which is
exactly the conflict of interest the skill is built for).

## Claimed
Scripts that find hallucinated APIs and untrustworthy tests, runnable from any
project.

## Actual
Initially, several of them only worked when invoked from the skill's own
directory, and one class of ordinary import was reported as hallucinated.

## Findings

### F1 — BLOCKER — `scripts/*.sh` — audit target is the wrong directory
The wrappers `cd` into the skill directory, then fall back to `os.getcwd()` for
the audit root — which is now the skill directory. Run from a user's project,
every probe audits the skill instead of the project.
- Repro: `cd ~/anyproject && ~/ai-code-audit/skills/ai-code-audit/scripts/check_imports.sh` → findings about `scripts/_lib.py`
- Fix: capture `ORIG=$(pwd)` before `cd`, default `AUDIT_ROOT` to it.

### F2 — BLOCKER — `scripts/probe_api.py:132` — `from pkg import submodule` reported as a hallucinated symbol
`from app import sdk` where `app/__init__.py` does not re-export `sdk` is
reported at `BLOCKER`. This is one of the most common Python import forms.
- Repro: fixture `evals/fixtures/hallucinated-api` before the fix → `'sdk' is imported from 'app' but not defined there`
- Fix: resolve a submodule next to the package (`sdk.py`, `sdk/__init__.py`);
  also try dotted-path suffixes so a monorepo root does not hide the package.
- Follow-up: the same gap existed one level down. `from app.payment_sdk import create`
  with no `payment_sdk` was reported as a *symbol* error, or silently dropped.
  Fixed by resolving dotted paths segment by segment and adding the
  `hallucinated-module` rule, covered by the same fixture.

### F3 — MAJOR — `scripts/slop_scan.sh` — silent no-op from any other directory
The script changes directory but forwards caller-relative paths, so each target
fails to open and is "skipped". Prints `0 finding(s)` and exits 0 — it looks
like a clean result.
- Fix: rewrite relative arguments against the captured original directory.
- Lesson worth keeping: a probe that cannot open its input must not report zero.

### F4 — MAJOR — `scripts/probe_api.py` — keyword-argument rule never fired
Modules are indexed under both their short and dotted names. `match_call`
counted both entries, saw two "importers", and bailed on every call.
- Repro: fixture `hallucinated-api` → `create_payment(total, retries=tries)` silent
- Fix: deduplicate by object identity before counting.

### F5 — MINOR — `scripts/_lib.py` — `tests.py` not recognised as a test file
Only `test_*.py`, `tests/`, `conftest.py` counted. `tests.py` and `test.py`
slipped through, so test-only behaviour (skip markers, `raises(Exception)`)
never applied to them.
- Fix: widen the predicate.

## Residual, accepted

### R1 — MAJOR — `check_imports.py:69` — swallowed exception
`except Exception: pass` around `importlib.metadata`. Deliberate: broken dist
metadata in an odd venv should not abort an audit. The rule cannot tell
deliberate from accidental; it stays. `mypy`/`ruff` would say the same.

### R2 — MINOR — `probe_api.py:90` — `except ValueError: pass`
`ast.literal_eval` on a non-literal `__all__`. Same reasoning, narrower scope.

### R3 — BLOCKER x4 in `check_imports` at the repo root, on fixtures
`evals/fixtures/*/app` are package fragments, not installable packages, and the
repo root has no `app`. Auditing the repo as a whole flags them. Expected;
auditing each fixture directory separately is clean. Documented in README as a
scope note.

## Verdict
**MERGE.** F1–F5 fixed and covered by fixtures. R1–R3 accepted with reasons.
The audit was run three times during the work, and the third pass is the one
above — the first two produced the findings, not the fixes.

## What this says about the skill

- The reverting of a used-directory-relative script is exactly a
  scope-creep-shaped bug: it worked in the author's cwd, nowhere else. A model
  reviewing its own output would have called the scripts "fine".
- F3 is the interesting one: the failure mode was *plausible output*, not an
  error. Green-looking results from a broken probe are the hardest thing here
  to catch, and the reason `SKILL.md` insists that skipped steps be carried into
  the report.

---

# Second pass: the TypeScript addition

Same conflict of interest, same rule: report what the probes found on new code.

## Claimed
The TS probes give TypeScript the same coverage without a fourth dependency.

## Actual
They do, at a cost the Python probes do not pay: without a stdlib TS parser,
imports and exports are read by regex. Two places where that shows:

### F6 — MAJOR — `_tslib.exported_names` — `export * from` is invisible
A name re-exported through a barrel file looks missing. Reporting it would be a
false positive on every `index.ts` in existence.
- Mitigation: `resolve` reports "unknown surface" for any module containing
  `export *`, and both `probe_api_ts` checks skip it. Coverage lost, FP avoided.
- Chosen because a wrong `BLOCKER` costs more than a missing one.

### F7 — MINOR — `slop_scan_ts.RULES` — `fetch-no-signal` is a window heuristic
`signal` is looked for within six lines of the `fetch` call. A signal built ten
lines earlier in a shared helper is not seen.
- Mitigation: `confidence: medium` on the rule, and the message says "without a
  signal" rather than asserting one is missing.
- Repro kept in `evals/fixtures/clean-ts/app/net.ts`, where the signal is on the
  next line and must stay quiet.

## Residual, accepted

### R4 — regex rules cannot see through comments
`strip_comments` removes `//` and `/* */` before structural matching, so prose
that mentions `innerHTML` does not fire. A URL inside a string can still fire a
`fetch` rule. Accepted; the alternative is a real parser.

## Verdict
**MERGE.** Both probes were run against `hallucinated-ts` and `clean-ts` and a
scratch project outside the repo (which is how F6 surfaced). The TS layer is
weaker than the Python layer by design and says so in `references/langs/ts.md`.

## What this says about the skill

- Adding a language forced a choice between precision and a fourth runtime
  dependency. The skill took the dependency-free side and wrote down what it
  costs — which is the same trade `SKILL.md` asks of every finding.
- The single strongest TS probe is not in this repo at all: it is `tsc --noEmit`
  in `static_gate_ts.sh`. Everything else only matters where `@ts-ignore` is.

---

# Third pass: Go and Rust

## Claimed
Go and Rust coverage at the same standard, keeping the "false positives are the
metric" rule.

## Actual
Both work on fixtures, but neither toolchain exists on the machine this was
written on, so `static_gate_go.sh` and `static_gate_rust.sh` have **never been
executed**. That is the largest open item in the package.

### F8 — MAJOR — `slop_scan_{go,rust}.RULES` — line-anchored rules never fired
Four Go rules compile with `^`…`$` and no `re.M`, so `^` only matched offset 0.
`empty-err-check`, `discarded-error`, `log-fatal` and `panic` were dead code.
- Repro: fixture `slop-go` → `response, _ := http.Get(url)` silent
- Fix: `re.compile(p.pattern, p.flags | re.M)` inside the loop.
- This is the F3 family again: a rule that cannot fire reports nothing, and
  nothing looks like success.

### F9 — BLOCKER — `check_imports_rust` — every braced `use` was unresolvable
`use crate::money::{Cents, total};` was split on `::`, so `{Cents` and `total}`
became path segments. Every braced import in every Rust file was a false
`BLOCKER`; `clean-rust` caught it on the first run.
- Fix: resolve the prefix before `{` and let `probe_api_rust` handle the names.

### F10 — MINOR — `slop_scan_go.defer_in_loop` — composite literals broke the match
`for _, u := range []string{"a","b"} {` — the first `{` after `for` is the slice
literal, so the brace counter closed before the loop body and `defer` was never
seen.
- Fix: brace from the last `{` on the loop's own line.

### F11 — MINOR — `slop_scan_go` — `empty-err-check` could not see an initializer
Only `if err != nil` matched, not `if err := f(); err != nil`.
- Fix: allow `if <stmt>; err != nil`.

## Residual, accepted

### R5 — MAJOR — `static_gate_{go,rust}.sh` unverified
Written from documented flags, never run. `cargo check` writing `target/` is
called out in `references/langs/rust.md`. First real repository audited with
either language should confirm the gate output before trusting the rest.

### R6 — MINOR — `probe_api_go` selector matching is textual
`pkg.X` inside a string or a struct literal key still matches. Severity is
`BLOCKER` only when the package is a local import, which keeps the noise low, but
a name that exists on another local package can be misattributed.

### R7 — MINOR — Rust `use` groups are only checked one level deep
`use crate::m::{a::{b, c}}` resolves `a` but not `b`/`c`. Nested groups are
uncommon enough that a wrong finding would cost more than the gap.

## Verdict
**MERGE WITH FIXES DONE.** F8–F11 fixed and covered. R5 is the honest asterisk:
Go and Rust are one notch below Python and TypeScript until someone runs the
gates on a real toolchain.

## What this says about the skill

- Three separate bugs were the same shape: *a probe that quietly matches
  nothing*. It is the dominant failure mode of this package, not of the code it
  reviews, and it is why every rule here needs a fixture that must fail first.
- Writing rules for a language whose compiler you cannot run is guesswork with a
  safety net. Writing them for one you can run is engineering. The gate scripts
  are the first thing to test in a real repo.
