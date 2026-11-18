# Rust specifics

Language-shaped versions of the general failure modes. Read before the sweep.

## The oracle

`cargo check` is the strongest single probe in this whole skill. If it is
available, a compile error is a fact and `#[allow(...)]` in the diff is how a
fact gets buried. `cargo clippy` covers most style ground, so the rules here
concentrate on completeness: stubs, dropped `Result`, panics in library code.

`cargo check` writes `target/`. That is the one place this skill is not purely
read-only — say so if the user cares.

## API surface that models invent most often

- `serde`: `#[serde(rename_all)]` forms, `Deserialize` on a borrowed type, `#[serde(flatten)]` with an enum
- `tokio`: `spawn` without `move`, `select!` arms missing a `,`, `block_on` inside async
- `Iterator`: `map` + `collect::<Result<_,_>>()` where `?` in a loop was meant
- `Option`/`Result`: `ok_or` vs `ok_or_else`, `?` inside a closure, `and_then` chains that swallow errors
- `bytes`/`str`: `&String` parameters, `String::from(&str)` where `.to_owned()` is idiomatic
- `chrono`/`time`: `Utc::now` in a library, naive vs aware confusion
- `HashMap`: `get(...).unwrap()` where `entry` API fits
- lifetimes: `'static` bounds added to make it compile, not because they are needed

## Rust-specific tells

| tell | consequence |
|---|---|
| `todo!()` / `unimplemented!()` | patch panics where a feature was claimed |
| `.unwrap()` in a library path | panic with no context |
| `.expect("")` | panic with no *useful* context |
| `let _ = ...` on a `Result` | `#[must_use]` silenced |
| `match x { _ => {} }` | the unhandled case disappears |
| `panic!` in a library | no recovery contract |
| `std::process::exit` | destructors skipped |
| `unsafe {}` without `// SAFETY:` | invariant undocumented |
| `as u32` | truncates silently; `try_from` is checked |
| `: String` parameter | forces an allocation the caller pays for |
| `#[ignore]` | test does not run in CI |
| `#[allow(dead_code)]` | unused code kept alive instead of used or deleted |

## Cheap probes beyond the gate

```bash
cargo check --message-format short
cargo fmt --check
cargo clippy -- -D warnings        # if installed
grep -c '#\[ignore\]' -r src/      # silences
```

## Manifest smells

- dependency added but not in `Cargo.toml` (`cargo add` never run)
- `edition` bumped inside an unrelated diff
- `[patch]`/`[replace]` sections added to paper over a version conflict
- a local `path = "../x"` dependency in a published crate
- version pin style changed (`"1.2"` → `"=1.2.3"`) without a reason
