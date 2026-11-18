#!/usr/bin/env python3
"""Imported Rust items that the target module never declares, or keeps private.

Usage: probe_api_rust.sh [paths...]
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _lib  # noqa: E402
import _rustlib  # noqa: E402


def check_file(path: str) -> list[_lib.Finding]:
    findings: list[_lib.Finding] = []
    source = _rustlib.strip_comments(_rustlib.read(path))

    for match in _rustlib.USE_LINE.finditer(source):
        text = match.group(1).strip()
        line = source.count("\n", 0, match.start()) + 1
        if not text.startswith("crate::"):
            continue
        body = text.split(" as ")[0]
        if "{" in body:
            prefix, rest = body.split("{", 1)
            imported = [part.strip() for part in rest.rstrip("}").split(",") if part.strip()]
            prefix_segments = [p for p in prefix.split("::") if p and p != "crate"]
            target_dir = _rustlib.resolve_module(prefix_segments, path)
            if target_dir is None:
                continue
            for name in imported:
                name = name.split(" as ")[0].strip()
                if not name:
                    continue
                if _rustlib.resolves_submodule(target_dir, name):
                    continue
                known = _rustlib.all_names(target_dir)
                is_pub = name in _rustlib.pub_names(target_dir)
                report(findings, path, line, target_dir, name, known, is_pub, match.group(0))
            continue

        segments = [p for p in body.split("::") if p and p != "crate"]
        if len(segments) < 2:
            continue
        name = segments[-1]
        target = _rustlib.resolve_module(segments[:-1], path)
        if target is None:
            continue
        if _rustlib.resolves_submodule(target, name):
            continue
        known = _rustlib.all_names(target)
        is_pub = name in _rustlib.pub_names(target)
        report(findings, path, line, target, name, known, is_pub, match.group(0))
    return findings


def report(findings, path, line, target, name, known, is_pub, evidence) -> None:
    if name in known and not is_pub:
        findings.append(_lib.Finding(
            rule="private-import", severity="MAJOR", file=_lib.rel(path), line=line,
            message=f"'{name}' is declared in {os.path.basename(target)} but not `pub`",
            evidence=evidence[:160], confidence="high",
        ))
        return
    if name in known:
        return
    findings.append(_lib.Finding(
        rule="undefined-import", severity="BLOCKER", file=_lib.rel(path), line=line,
        message=f"'{name}' is not declared in {os.path.basename(target)}",
        evidence=evidence[:160], confidence="high",
    ))


def main(argv: list[str]) -> int:
    files = argv or _rustlib.rust_files()
    if not files:
        _lib.skipped("probe_api_rust", "no Rust files")
        return 0
    findings: list[_lib.Finding] = []
    for path in files:
        findings.extend(check_file(path))
    unique = {(f.rule, f.file, f.line, f.message): f for f in findings}
    ordered = sorted(unique.values(), key=lambda f: (f.file, f.line))
    for finding in ordered:
        finding.emit()
    _lib.finish(ordered)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
