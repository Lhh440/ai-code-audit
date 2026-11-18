#!/usr/bin/env python3
"""Unresolvable Rust `use` paths: hallucinated modules and missing crates.

Usage: check_imports_rust.sh [paths...]
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _lib  # noqa: E402
import _rustlib  # noqa: E402


USAGE = """
`use` path and crate resolution for Rust.

usage: check-imports-rust [-h] [paths...]

Without paths, scans $AUDIT_ROOT (default: the directory the wrapper was run in).

Reads: .rs files and Cargo.toml. Writes: nothing.
Findings: unresolvable-crate/-module BLOCKER, undeclared-crate BLOCKER.

Exit: 0 even with findings; findings go to stdout as JSON lines.
"""

def segments_of(path_text: str) -> list[str]:
    """Path segments only; a braced group resolves against the prefix."""
    cleaned = path_text.split("{")[0] if "{" in path_text else path_text
    cleaned = cleaned.strip().strip("{}").strip().rstrip(":")
    cleaned = cleaned.split(" as ")[0]
    return [part for part in cleaned.split("::") if part not in ("", "*")]


def check_file(path: str, crates: set[str]) -> list[_lib.Finding]:
    findings: list[_lib.Finding] = []
    source = _rustlib.strip_comments(_rustlib.read(path))

    for match in _rustlib.EXTERN_CRATE.finditer(source):
        name = match.group(1)
        if name in _rustlib.CRATES_BUILTIN or name in crates:
            continue
        findings.append(_lib.Finding(
            rule="undeclared-crate", severity="BLOCKER", file=_lib.rel(path),
            line=source.count("\n", 0, match.start()) + 1,
            message=f"extern crate '{name}' is not in Cargo.toml",
            evidence=match.group(0), confidence="high",
        ))

    for match in _rustlib.USE_LINE.finditer(source):
        line = source.count("\n", 0, match.start()) + 1
        segments = segments_of(match.group(1))
        if not segments:
            continue
        root_segment = segments[0]

        if root_segment in ("crate", "self", "super"):
            rest = segments[1:]
            if not rest:
                continue
            if root_segment == "crate":
                if _rustlib.resolve_module(rest, path) is None:
                    findings.append(_lib.Finding(
                        rule="unresolvable-module", severity="BLOCKER", file=_lib.rel(path),
                        line=line, message=f"no module file for 'crate::{ '::'.join(rest) }'",
                        evidence=match.group(0)[:160], confidence="high",
                    ))
            continue

        if root_segment in _rustlib.CRATES_BUILTIN:
            continue
        if root_segment in crates:
            continue
        findings.append(_lib.Finding(
            rule="unresolvable-crate", severity="BLOCKER", file=_lib.rel(path), line=line,
            message=f"crate '{root_segment}' is not declared in Cargo.toml",
            evidence=match.group(0)[:160], confidence="high",
        ))
    return findings


def main(argv: list[str]) -> int:
    _lib.usage(argv, USAGE)
    files = argv or _rustlib.rust_files()
    if not files:
        _lib.skipped("check_imports_rust", "no Rust files")
        return 0
    if not _rustlib.cargo_manifest():
        _lib.skipped("check_imports_rust", "no Cargo.toml; crate checks disabled partially")
    crates = _rustlib.declared_crates()
    findings: list[_lib.Finding] = []
    for path in files:
        findings.extend(check_file(path, crates))
    findings.sort(key=lambda f: (f.file, f.line))
    for finding in findings:
        finding.emit()
    _lib.finish(findings)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
