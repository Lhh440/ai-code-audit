# ai-code-audit

A skill for reviewing code an **agent** wrote, where the same author also wrote
the tests and the diff is too large to read line by line.

Python, TypeScript, Go and Rust.

It does not review "code quality". It goes after the failure modes that are
specific to generated code — hallucinated APIs, optimistic paths, weakened
tests, near-miss copy/paste — and it refuses to report a finding without
evidence.

```
/app/billing.py:88  BLOCKER  hallucinated symbol
  client.create_charge(amount=...) — 2.4.1 exposes create_payment
  evidence  probe_api:88 · python -c "import stripe; help(stripe.Charge)"
  repro     pytest tests/test_billing.py::test_charge → AttributeError
```

## The one mechanism that matters

If the model wrote the tests, **a green suite is not evidence**. So one probe
stashes the implementation, keeps the tests, and re-runs them:

```
== revert-check ==
! 6 changed tests still pass WITHOUT the implementation.
  These assertions do not pin the new behaviour; treat the green suite as no evidence.
```

Almost nothing else does this. It is the reason the skill exists.

## Install

```bash
pi install git:github.com/<you>/ai-code-audit@v0.1.0
```

Then, inside the repo you want audited:

```
/skill:ai-code-audit review the diff against main
```

Or run the probes directly, no agent involved:

```bash
skills/ai-code-audit/scripts/survey.sh main
skills/ai-code-audit/scripts/probe_api.sh
skills/ai-code-audit/scripts/test_credibility.sh main
```

Directories are discovered, or set `AUDIT_FILES` / pass paths explicitly.

## What it runs

| probe | finds |
|---|---|
| `survey.sh` | ranks changed files by risk, hides generated/vendored |
| `check_imports.sh` | unresolvable modules, undeclared dependencies |
| `probe_api.sh` | imported symbols that do not exist, keyword args the function never accepted |
| `static_gate.sh` | `py_compile`, `ruff`, `mypy` — never mutating |
| `test_credibility.sh` | skip markers, deleted asserts, and the revert-check |
| `slop_scan.sh` | 17 Python AST + 3 line rules; ast-grep when installed |
| `check_imports_ts.sh` / `probe_api_ts.sh` | unresolvable modules; imported names the module never exports |
| `static_gate_ts.sh` | `tsc --noEmit`, `eslint` — never mutating |
| `slop_scan_ts.sh` | 23 regex rules; ast-grep ruleset `rules/ai-slop-ts.yml` when installed |
| `check_imports_go.sh` / `probe_api_go.sh` | unresolvable import paths; undefined or unexported selectors |
| `static_gate_go.sh` | `gofmt -l`, `go vet` |
| `slop_scan_go.sh` | 21 regex rules; ast-grep ruleset `rules/ai-slop-go.yml` when installed |
| `check_imports_rust.sh` / `probe_api_rust.sh` | unresolvable `use` paths; items never declared or not `pub` |
| `static_gate_rust.sh` | `cargo fmt --check`, `cargo check` |
| `slop_scan_rust.sh` | 21 regex rules; ast-grep ruleset `rules/ai-slop-rust.yml` when installed |

Everything is stdlib Python 3.9+. No install step, no dependencies. Missing
tools degrade to `skipped:`, which the report must carry forward — a skipped
step is not a pass.

## Design rules

- **Read-only by default.** Fixes only on request, only after the report.
- **Evidence or it didn't happen.** No reproduction means the finding is
  demoted to "suspected" with the missing evidence named.
- **Style is not a finding.** Formatting and naming live in `NIT` and stay out
  of the verdict.
- **Report, then verdict.** Every report ends with `BLOCK` / `MERGE WITH FIXES`
  / `MERGE` and the conditions.
- **False positives are the metric.** `evals/` keeps two fixtures of odd-but-
  correct code, and both must stay green.

## Layout

```
skills/ai-code-audit/
├── SKILL.md              the 6-step procedure
├── scripts/              probes (_lib.py holds shared finding emitter)
├── rules/ai-slop-*.yml   ast-grep rulesets per language
└── references/
    ├── failure-modes.md  10 modes, each with a probe
    ├── report.md         output format
    └── langs/{py,ts,go,rust}.md
evals/                    fixtures + harness (run.sh)
docs/self-audit.md        this skill audited by itself
```

## Scope

Python, TypeScript, Go and Rust. Each language ships its own reference file, probe set,
and ast-grep ruleset, and `SKILL.md` routes by file type — no shared "best
practice" soup. Adding a third means the same three files; see `CONTRIBUTING.md`.

TypeScript gets no less rigour than Python, but a different kind: `tsc --noEmit`
is a real oracle, so the TS probes spend their effort on `// @ts-ignore`,
unresolvable modules, and exported-name mismatches — the places the compiler is
told to look away.

Not in scope: formatting, naming, architecture review, auto-fix.

## License

MIT.
