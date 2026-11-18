# Changelog

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
