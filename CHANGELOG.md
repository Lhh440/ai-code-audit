# Changelog

## [0.4.0] - 2026-01-01

- `test_credibility.sh`: TypeScript, Go and Rust support. Test files are
  classified per language and run with the project's own runner; the
  revert-check stashes only implementation files, then restores them.
- `--help` on the static gates, `survey.sh` and `test_credibility.sh`, completing
  the per-probe documentation promise
- `static_gate.sh` resolves relative path arguments against `AUDIT_ROOT`
  instead of the skill directory
- slop scanners keep line numbers stable across block comments; TypeScript
  structural rules now read comment-stripped source while comment rules read
  the original
- fix `bool-identity` flagging `x is None`; `raises-exception` flagging every
  `pytest.raises`, and `open(..., "r")` slipping past `open-without-encoding`
- regression coverage for the three false positives in `clean-unusual`
- drop the stray empty `hi` file

## [0.3.1] - 2026-01-01

- `--help` on every probe: what it reads, writes, and flags
- `SECURITY.md`: full write surface, the worktree risk, sandboxing notes
- wrappers no longer mangle `-` arguments into paths

## [0.3.0] - 2026-01-01

Go and Rust support.

- Probes per language: `check_imports_{go,rust}`, `probe_api_{go,rust}`,
  `slop_scan_{go,rust}`, `static_gate_{go,rust}`
- Go rules: `empty-err-check`, `nil-err-return`, `http-default-client`,
  `defer-in-loop`, `blank-err-assign`, `unexported-selector`, 15 more
- Rust rules: `todo-macro`, `discarded-result`, `private-import`,
  `undefined-import`, `unsafe-no-safety-note`, `empty-match-arm`, 15 more
- `cargo check` writes `target/`; noted as the one non-read-only step
- Fixtures: 2 planted-defect sets, 2 clean sets

## [0.2.0] - 2026-01-01

TypeScript support.

- Probes: `check_imports_ts`, `probe_api_ts`, `slop_scan_ts`, `static_gate_ts`
- Rules: `hallucinated-export`, `missing-default-export`, `hallucinated-module`,
  `empty-catch`, `innerhtml`, `fetch-no-signal`, `nonnull-env`, `any-type`,
  `sort-no-comparator`, `ts-nocheck`, `near-miss-copy` and 14 more
- ast-grep ruleset `ai-slop-ts.yml`; regex fallback when ast-grep is absent
- `test_credibility.sh` shared across both languages
- Fixtures: 1 planted-defect TS set, 1 clean TS set

## [0.1.0] - 2026-01-01

Initial release.

- Skill: `ai-code-audit` (claimed-vs-actual frame, evidence-first rules, graded output)
- Probes: `check_imports`, `probe_api`, `static_gate`, `test_credibility`, `slop_scan`
- 17 AST rules incl. `near-miss-copy` and hallucinated-symbol detection
- ast-grep ruleset with stdlib AST fallback when ast-grep is absent
- Eval harness: 4 planted-defect fixtures, 2 clean-code fixtures for false positives
