# Security

Skills run programs and steer a model. This is what this one does, so you can
decide before installing rather than after.

## What actually executes

Everything is in `skills/ai-code-audit/` and is plain Python 3 (stdlib only) plus
POSIX shell. **~1,400 lines total, no dependencies, no build step, no install
script.** There is no `postinstall`, no network call, no telemetry, no bundled
binary.

The model reads `SKILL.md` and then runs the probe scripts. It does not run
anything else.

## Writes, in full

| step | writes |
|---|---|
| `check_imports*`, `probe_api*`, `slop_scan*` | nothing |
| `static_gate.sh` | `__pycache__/` via `py_compile`; mypy cache in `/tmp` |
| `static_gate_ts.sh` | nothing (eslint runs `--no-fix`) |
| `static_gate_go.sh` | nothing |
| `static_gate_rust.sh` | `target/` via `cargo check` |
| `test_credibility.sh` | **the git worktree** — see below |
| `survey.sh` | a file list in `/tmp` |

Nothing writes outside the audited repo except `/tmp`.

## The one risky step

`test_credibility.sh` performs `git stash push` on changed non-test files, runs
the changed tests with the language's own runner (`pytest`, a local `vitest` or
`jest`, `go test`, or `cargo test`), then `git stash pop`. Consequences:

- Uncommitted work in those files is stashed for the duration. If the shell is
  killed mid-run, `git stash list` still holds it.
- It runs your test suite, which may itself touch the filesystem, network, or a
  database. For Go and Rust the toolchains may fetch modules or crates.
- Use `--no-revert` to keep it to the read-only pattern scan.
- Rust inline `#[cfg(test)]` modules live in the reverted source files, so only
  integration tests under `tests/` can be used for the revert-check.

Run it on a clean tree the first time.

## Network

No probe makes a network request. `check_imports*` resolves packages from
`node_modules/`, `go.mod`, `Cargo.toml`, and installed dist metadata — locally.
`static_gate_rust.sh`/`static_gate_go.sh` inherit whatever your `cargo`/`go`
config does, which can include fetching crates or modules.

## What it trusts

- `AUDIT_ROOT` and `AUDIT_FILES` environment variables
- every tool on `PATH` (`git`, `python3`, `ruff`, `tsc`, `go`, `cargo`, `ast-grep`)
- the audited repo's own `package.json`, `go.mod`, `Cargo.toml` — for names only,
  never executed

A malicious `package.json` cannot execute anything by being read. A malicious
`conftest.py` can, because `pytest` imports it — that risk is inherent to running
a test suite and is not introduced here.

## Reviewing before you install

```bash
git clone https://github.com/Lhh440/ai-code-audit && cd ai-code-audit
wc -l skills/ai-code-audit/scripts/* skills/ai-code-audit/SKILL.md
grep -rn "curl\|wget\|http\|eval\|exec" skills/ai-code-audit/scripts/*.py
./evals/run.sh          # 15 fixtures, no network needed
```

Then run it on a repo you already understand and read the findings against the
code. A scanner that is wrong about code you know is wrong about code you don't.

## Sandboxing

The probes need no privileges and no network, so they run fine in a container
with the repo mounted read-write and nothing else. The skill only degrades to
`skipped:` when a tool is missing.

## Supported

Current `main`. There are no releases older than `0.3.0` worth pinning.

## Reporting

Open an issue for anything suspicious. For something that could run code the
probes do not document above, say so in the title with `security:` and avoid
public detail until it is confirmed — there is no private channel beyond that.
