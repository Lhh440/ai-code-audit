# Contributing

## The bar

A new rule must earn its false-positive budget. Add the fixture first:

1. Drop a minimal, realistic example under `evals/fixtures/<rule>/`.
2. Append the rule id to that fixture's `expect.txt`.
3. Run `evals/run.sh` — it must fail.
4. Implement, until it passes.
5. Run `evals/run.sh` again: `clean-*` fixtures must stay green.

If a rule fires on `clean-unusual` or `clean-types`, either narrow it or add
the counter-example there so the FP stays visible.

## Adding a rule

- Shape rules go in `rules/ai-slop.yml` (ast-grep) **and** `slop_scan.py`
  (stdlib fallback). Both paths must stay in sync.
- Severity: `BLOCKER` only for things that are wrong at runtime. Taste is `NIT`.
- Rules must be language-local and side-effect free.

## Targeting another language

Copy the four existing shapes — `py` for an AST oracle-less language, `ts`/`go`/`rust`
for regex plus compiler — add
`references/langs/<lang>.md`, a `*_<lang>.py` probe set plus `rules/ai-slop-<lang>.yml`,
and a gate in `SKILL.md` step 2. Keep every language in one package; do not fork
the skill.

Existing precedent: TypeScript, Go and Rust use regexes where Python uses `ast`,
because no parser for them is available in the stdlib. Say which trade-off a new
language makes in its reference file — precision against dependency weight — and
name its compiler oracle in the first paragraph.

## Commits

`rule(<lang>): <what>` for scanners, `docs:`, `fix:`. One rule per commit.
