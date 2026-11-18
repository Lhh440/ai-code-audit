#!/usr/bin/env python3
"""Find unresolvable TypeScript/JavaScript imports and undeclared dependencies.

Usage: check_imports_ts.sh [paths...]
Exit:  0 always (findings are data, not failure)
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _lib  # noqa: E402
import _tslib  # noqa: E402


USAGE = """
Import resolution for TypeScript: unresolvable specs, undeclared packages.

usage: check-imports-ts [-h] [paths...]

Without paths, scans $AUDIT_ROOT (default: the directory the wrapper was run in).

Reads: .ts/.tsx/.js files and package.json. Writes: nothing.
Findings: unresolvable-import BLOCKER, missing-dependency MAJOR, undeclared-dependency MINOR.

Exit: 0 even with findings; findings go to stdout as JSON lines.
"""

def check_file(path: str, declared: set[str]) -> list[_lib.Finding]:
    findings: list[_lib.Finding] = []
    source = _tslib.strip_comments(_tslib.read(path))
    for line, spec in _tslib.specs(source):
        if spec.startswith("."):
            if _tslib.resolve_relative(spec, path) is None:
                findings.append(_lib.Finding(
                    rule="unresolvable-import", severity="BLOCKER", file=_lib.rel(path),
                    line=line, message=f"relative import '{spec}' resolves to no file",
                    evidence=spec, confidence="high",
                ))
            continue
        if spec.startswith(("node:", "http:", "https:", "data:", "bun:", "deno:")):
            continue
        if spec in _tslib.NODE_BUILTINS or spec.split("/")[0] in _tslib.NODE_BUILTINS:
            if f"@types/node" not in declared:
                findings.append(_lib.Finding(
                    rule="missing-types", severity="MINOR", file=_lib.rel(path), line=line,
                    message="imports a Node builtin but @types/node is not declared",
                    evidence=spec, confidence="medium",
                ))
            continue
        name = _tslib.package_name(spec)
        if name in declared:
            if not _tslib.has_node_modules(name):
                findings.append(_lib.Finding(
                    rule="missing-dependency", severity="MAJOR", file=_lib.rel(path), line=line,
                    message=f"'{name}' is declared but not installed",
                    evidence=spec, confidence="high",
                ))
            continue
        if _tslib.has_node_modules(name):
            findings.append(_lib.Finding(
                rule="undeclared-dependency", severity="MINOR", file=_lib.rel(path), line=line,
                message=f"'{name}' is imported but missing from package.json",
                evidence=spec,
            ))
            continue
        findings.append(_lib.Finding(
            rule="unresolvable-import", severity="BLOCKER", file=_lib.rel(path), line=line,
            message=f"cannot resolve package '{name}' (not declared, not in node_modules)",
            evidence=spec, confidence="high",
        ))
    return findings


def main(argv: list[str]) -> int:
    _lib.usage(argv, USAGE)
    files = argv or _tslib.ts_files()
    if not files:
        _lib.skipped("check_imports_ts", "no TypeScript files")
        return 0
    declared = _tslib.declared_dependencies()
    findings: list[_lib.Finding] = []
    for path in files:
        findings.extend(check_file(path, declared))
    findings.sort(key=lambda f: (f.file, f.line))
    for finding in findings:
        finding.emit()
    _lib.finish(findings)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
