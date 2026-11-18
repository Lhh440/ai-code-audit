#!/usr/bin/env python3
"""Unresolvable Go imports: hallucinated package paths and missing requires.

Usage: check_imports_go.sh [paths...]
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _golib  # noqa: E402
import _lib  # noqa: E402


def check_file(path: str, required: set[str]) -> list[_lib.Finding]:
    findings: list[_lib.Finding] = []
    module = _golib.module_path()
    for line, spec, alias in _golib.imports(_golib.strip_comments(_golib.read(path))):
        if spec.startswith(("http://", "https://")):
            continue
        if _golib.resolve_import(spec) is not None:
            continue
        if _golib.required_by_prefix(spec, required):
            if not os.path.isdir(os.path.join(_golib.root(), "vendor")):
                findings.append(_lib.Finding(
                    rule="unvendored-dependency", severity="NIT", file=_lib.rel(path),
                    line=line, message=f"'{spec}' is required but no vendor/ directory exists",
                    evidence=spec, confidence="low",
                ))
            continue
        hint = ""
        if module and not spec.startswith(module) and "/" in spec:
            hint = f" (module is '{module}')"
        findings.append(_lib.Finding(
            rule="unresolvable-import", severity="BLOCKER", file=_lib.rel(path),
            line=line, message=f"cannot resolve import '{spec}'{hint}",
            evidence=spec, confidence="high",
        ))
    return findings


def main(argv: list[str]) -> int:
    files = argv or _golib.go_files()
    if not files:
        _lib.skipped("check_imports_go", "no Go files")
        return 0
    required = _golib.required_modules()
    findings: list[_lib.Finding] = []
    for path in files:
        findings.extend(check_file(path, required))
    findings.sort(key=lambda f: (f.file, f.line))
    for finding in findings:
        finding.emit()
    _lib.finish(findings)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
