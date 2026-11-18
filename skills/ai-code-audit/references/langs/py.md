# Python specifics

Language-shaped versions of the general failure modes. Read before the sweep.

## API surface that models invent most often

Check each against the installed version, not against memory.

- `requests`: `timeout=` omitted, `Session.request` kwargs, `.json` on a non-JSON body
- `pytest`: `@pytest.mark.parametrize` argument order, `tmp_path` vs `tmpdir`, `monkeypatch.setattr` with three args in the wrong order
- `pathlib`: `Path.read_text(encoding)`, `/` joining with a `str` on the right
- `asyncio`: `asyncio.run` inside a running loop, `gather` without `return_exceptions`, awaiting a non-awaitable
- `dataclasses`: `field(default_factory=...)` where a plain default was written, `frozen=True` with mutation
- `typing`: `Optional` without a `None` branch, `dict[str, X]` on Python < 3.9, `TypeVar` never bound
- `logging`/`unittest.mock`: `assert_called_once_with` on an unpatched symbol, `mock.patch` target string that no longer matches after a rename

## Cheap correctness probes

```bash
python3 -m py_compile <file>            # syntax
python3 -m compileall -q <pkg>          # whole package
python3 -c "import <mod>; help(<mod>.<fn>)"   # real signature
pytest <file> -q --collect-only         # fixtures and marks resolve
pip show <dist> | head -3               # version the probe ran against
```

## Python-specific tells and why they matter

| tell | consequence |
|---|---|
| `except Exception: pass` | failure becomes silence; caller cannot branch |
| `assert` for runtime validation | vanishes under `python -O` |
| mutable default `def f(x=[])` | state leaks between calls |
| `open()` without `encoding=` | mojibake on non-UTF-8 hosts |
| f-string into `cursor.execute` | injection; values are not bound |
| `requests.get` without `timeout` | process hangs, no traceback |
| `datetime.utcnow()` | naive datetimes, wrong under non-UTC |
| `as any`-equivalent `# type: ignore` | the mismatch it hides stays |
| `sys.path.append` in library code | import order dependent on cwd |
| module-level mutable state | test order dependence |
| `__init__.py` doing work | import side effects, circular imports |

## Packaging diff smells

- dependency added to `requirements.txt` but not to `pyproject.toml`, or vice versa
- pin style changed (`==` → `>=`) inside an unrelated diff
- `python_requires` lowered without checking syntax against it
- new `setup.py` next to an existing `pyproject.toml`
- wheel data files added without an entry in the manifest
