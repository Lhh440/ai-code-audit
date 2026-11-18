---
name: ai-code-audit
description: Audit AI-generated Python, TypeScript, Go or Rust code for hallucinated APIs, weakened tests, optimistic paths, over-engineering, and fake completeness. Use when reviewing a diff or PR that an agent wrote, when the same author also wrote the tests, or when the diff is too large to read line by line.
license: MIT
compatibility: Requires bash, python3 >= 3.9. Optional git, ruff, mypy, pytest, tsc, eslint, go toolchain, cargo/clippy, ast-grep. Scripts degrade when a tool is missing.
---

# AI code audit

You are auditing code whose author was a model. The goal is **evidence about correctness**, not conformance to your taste.

The default is read-only. Do not edit files unless the user asks for fixes, and then only after the report exists.

Three rules that carry this whole skill:

1. **The author wrote the tests.** A green suite proves little until you check the suite still fails when the implementation is reverted.
2. **A finding needs evidence.** A command output line or the offending source. No evidence means it goes in the "suspected" bucket with a note about what is missing.
3. **Style is not a finding.** Formatting, naming, and import order go to NIT and stay out of the verdict.

## 0. Fix the target

Read the task description, issue, commit message, or the user's stated intent. Write one sentence: *what this code claims to accomplish*. Review against that sentence, not against how you would have written it. If no intent is recoverable, say so and audit for internal consistency only.

## 1. Survey

Run `scripts/survey.sh`. It ranks files by risk and marks generated artifacts, lockfiles, and vendored trees. If the diff exceeds 400 lines, work slice by slice in risk order — never a linear readthrough.

## 2. Collect evidence (read-only)

Pick the probe set by file type. All steps, before any conclusions are written.

**Python**

```bash
scripts/check_imports.sh     # unresolvable imports, packages absent from dependencies
scripts/probe_api.sh         # symbols that do not exist in the imported module, bad kwargs
scripts/static_gate.sh       # py_compile / ruff / mypy, non-mutating
scripts/test_credibility.sh  # skip markers, weakened asserts, revert-check
scripts/slop_scan.sh         # ai-slop rules; ast-grep if installed, else AST fallback
```

**TypeScript**

```bash
scripts/check_imports_ts.sh  # unresolvable modules, undeclared or uninstalled packages
scripts/probe_api_ts.sh      # imported names the module never exports
scripts/static_gate_ts.sh    # tsc --noEmit / eslint, non-mutating
scripts/test_credibility.sh  # same revert-check; uses a local vitest or jest
scripts/slop_scan_ts.sh      # regex rules; ast-grep rules/ai-slop-ts.yml when installed
```

**Go**

```bash
scripts/check_imports_go.sh  # unresolvable import paths, missing requires
scripts/probe_api_go.sh      # undefined and unexported selectors on local packages
scripts/static_gate_go.sh    # gofmt -l / go vet, non-mutating
scripts/test_credibility.sh  # skip markers, deleted asserts, and the revert-check
scripts/slop_scan_go.sh      # regex rules; ast-grep rules/ai-slop-go.yml when installed
```

**Rust**

```bash
scripts/check_imports_rust.sh  # unresolvable use paths, undeclared crates
scripts/probe_api_rust.sh      # imported items never declared, or not `pub`
scripts/static_gate_rust.sh    # cargo fmt --check / cargo check
scripts/test_credibility.sh    # integration tests under tests/ only
scripts/slop_scan_rust.sh      # regex rules; ast-grep rules/ai-slop-rust.yml when installed
```

Mixed repos: run each set on its own files.

Record which steps were skipped for missing tools, and carry that into the report. A skipped step is not a pass. Where a real oracle exists, it outranks every heuristic here: `tsc --noEmit`
for TypeScript, `go vet` for Go, `cargo check` for Rust. The remaining probes
matter most exactly where that oracle is silenced — `// @ts-ignore`,
`//nolint`, `#[allow(...)]`, empty error branches.

## 3. Failure-mode sweep

Walk `references/failure-modes.md` in order. On a hit, record `file:line`.

Language specifics: `references/langs/<lang>.md` — `py`, `ts`, `go` or `rust`.
Read the matching file before step 3.

## 4. Grade

- `BLOCKER` — wrong, crashes, leaks, or loses data
- `MAJOR` — works today, will hurt soon
- `MINOR` — real but contained
- `NIT` — linter territory

Every finding carries: evidence, consequence, reproduction, confidence. Downgrade to "suspected" and name the missing evidence when you cannot produce a reproduction. **Do not inflate the count.** A report with 4 real findings beats one with 20 where 12 are taste.

## 5. Output

Use the table in `references/report.md`. Lead with claimed-versus-actual, then findings, then end with the verdict line: can this merge, and under what conditions.

## 6. Fixes (only when asked)

Report first, then patch, then re-run step 2 in full. Never fix and grade in the same pass.
