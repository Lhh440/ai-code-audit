#!/usr/bin/env python3
"""Undefined and unexported identifiers referenced through local Go packages.

Usage: probe_api_go.sh [paths...]
"""

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _golib  # noqa: E402
import _lib  # noqa: E402

# package.name where package is a lower-case identifier
SELECTOR = re.compile(r"(?<![\w.])([a-z]\w*)\.([A-Za-z_]\w*)")


USAGE = """
Undefined and unexported selectors on local Go packages.

usage: probe-api-go [-h] [paths...]

Without paths, scans $AUDIT_ROOT (default: the directory the wrapper was run in).

Reads: local packages. Writes: nothing.
Findings: undefined-symbol BLOCKER, unexported-selector MAJOR.

Exit: 0 even with findings; findings go to stdout as JSON lines.
"""

def aliases(path: str) -> dict[str, str]:
    """alias -> resolved package directory for local packages only."""
    out: dict[str, str] = {}
    for _line, spec, alias in _golib.imports(_golib.strip_comments(_golib.read(path))):
        target = _golib.resolve_import(spec)
        if target is None or target == spec:
            continue
        if not os.path.isdir(target):
            continue
        name = alias if alias and alias not in {"_", "."} else _golib.package_name(target)
        out[name] = os.path.abspath(target)
    return out


def check_file(path: str, symbols: dict[str, set[str]]) -> list[_lib.Finding]:
    findings: list[_lib.Finding] = []
    source = _golib.strip_comments(_golib.read(path))
    table = aliases(path)
    if not table:
        return findings

    for match in SELECTOR.finditer(source):
        package_alias, symbol = match.group(1), match.group(2)
        directory = table.get(package_alias)
        if directory is None:
            continue
        known = symbols.get(directory, set())
        if symbol in known:
            continue
        line = source.count("\n", 0, match.start()) + 1
        if symbol[0].islower() and _declared_lowercase(directory, symbol):
            findings.append(_lib.Finding(
                rule="unexported-selector", severity="MAJOR", file=_lib.rel(path), line=line,
                message=f"'{symbol}' exists in {os.path.basename(directory)} but is not exported",
                evidence=match.group(0), confidence="medium",
            ))
            continue
        findings.append(_lib.Finding(
            rule="undefined-symbol", severity="BLOCKER", file=_lib.rel(path), line=line,
            message=f"'{symbol}' is not declared in package {os.path.basename(directory)}",
            evidence=match.group(0), confidence="high",
        ))
    return findings


def _declared_lowercase(directory: str, symbol: str) -> bool:
    pattern = re.compile(rf"(?m)^(?:func\s+(?:\([^)]*\)\s*)?|type\s+|var\s+|const\s+){re.escape(symbol)}\b")
    for name in os.listdir(directory):
        if name.endswith(".go") and pattern.search(_golib.read(os.path.join(directory, name))):
            return True
    return False


def main(argv: list[str]) -> int:
    _lib.usage(argv, USAGE)
    files = argv or _golib.go_files()
    if not files:
        _lib.skipped("probe_api_go", "no Go files")
        return 0
    symbols = _golib.package_symbols()
    findings: list[_lib.Finding] = []
    for path in files:
        findings.extend(check_file(path, symbols))
    unique = {(f.rule, f.file, f.line, f.message): f for f in findings}
    ordered = sorted(unique.values(), key=lambda f: (f.file, f.line))
    for finding in ordered:
        finding.emit()
    _lib.finish(ordered)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
