#!/usr/bin/env python3
"""Detect imported names a local module never exports, plus missing default exports.

Only local, unresolved-ambiguity-free cases are reported: a re-export via
`export * from` disables the name check for that module, because the real
surface then lives elsewhere.

Usage: probe_api_ts.sh [paths...]
"""

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _lib  # noqa: E402
import _tslib  # noqa: E402

NAMED = re.compile(r"""import\s+(?:type\s+)?\{([^}]*)\}\s*from\s*['"]([^'"]+)['"]""")
DEFAULT = re.compile(r"""import\s+(?:type\s+)?(\w+)\s*(?:,\s*\{[^}]*\})?\s+from\s*['"]([^'"]+)['"]""")
NAMESPACE = re.compile(r"""import\s+\*\s+as\s+(\w+)\s+from\s*['"]([^'"]+)['"]""")
STAR_REEXPORT = re.compile(r"""export\s+\*\s+from\s+['"]""")


def surface(path: str) -> tuple[set[str], bool, bool]:
    """(exported names, has default, has export *)"""
    source = _tslib.read(path)
    names, has_default = _tslib.exported_names(source)
    return names, has_default, bool(STAR_REEXPORT.search(source))


def bindings(block: str) -> list[str]:
    out = []
    for piece in block.split(","):
        piece = piece.strip()
        if not piece:
            continue
        piece = re.sub(r"^type\s+", "", piece)
        piece = piece.split(" as ")[0].strip()
        if piece.startswith("{"):
            continue
        out.append(piece)
    return out


def check_file(path: str, cache: dict[str, tuple[set[str], bool, bool]]) -> list[_lib.Finding]:
    findings: list[_lib.Finding] = []
    source = _tslib.strip_comments(_tslib.read(path))
    namespaces: dict[str, str] = {}

    def surface_of(spec: str) -> tuple[str, tuple[set[str], bool, bool]] | None:
        target = _tslib.resolve_relative(spec, path)
        if target is None:
            return None
        if target not in cache:
            cache[target] = surface(target)
        return target, cache[target]

    for match in NAMED.finditer(source):
        block, spec = match.group(1), match.group(2)
        line = source.count("\n", 0, match.start()) + 1
        resolved = surface_of(spec)
        if resolved is None:
            continue
        target, (exported, _default, star) = resolved
        if star:
            continue
        for imported in bindings(block):
            if imported == "default":
                continue
            if imported not in exported:
                findings.append(_lib.Finding(
                    rule="hallucinated-export", severity="BLOCKER", file=_lib.rel(path),
                    line=line, message=f"'{imported}' is imported but not exported by {_lib.rel(target)}",
                    evidence=match.group(0).splitlines()[0][:160], confidence="high",
                ))

    for match in DEFAULT.finditer(source):
        _local, spec = match.group(1), match.group(2)
        if match.group(0).lstrip().startswith("import *"):
            continue
        line = source.count("\n", 0, match.start()) + 1
        resolved = surface_of(spec)
        if resolved is None:
            continue
        target, (_exported, has_default, _star) = resolved
        if not has_default:
            findings.append(_lib.Finding(
                rule="missing-default-export", severity="BLOCKER", file=_lib.rel(path),
                line=line, message=f"default-imports {_lib.rel(target)}, which has no default export",
                evidence=match.group(0).splitlines()[0][:160], confidence="high",
            ))

    for match in NAMESPACE.finditer(source):
        alias, spec = match.group(1), match.group(2)
        resolved = surface_of(spec)
        if resolved is not None:
            namespaces[alias] = resolved[0]

    for alias, target in namespaces.items():
        exported, _default, star = cache[target]
        if star:
            continue
        for member in re.finditer(rf"\b{re.escape(alias)}\.(\w+)", source):
            if member.group(1) not in exported:
                findings.append(_lib.Finding(
                    rule="hallucinated-export", severity="BLOCKER", file=_lib.rel(path),
                    line=source.count("\n", 0, member.start()) + 1,
                    message=f"'{alias}.{member.group(1)}' is not exported by {_lib.rel(target)}",
                    evidence=member.group(0), confidence="high",
                ))
    return findings


def main(argv: list[str]) -> int:
    files = argv or _tslib.ts_files()
    if not files:
        _lib.skipped("probe_api_ts", "no TypeScript files")
        return 0
    cache: dict[str, tuple[set[str], bool, bool]] = {}
    findings: list[_lib.Finding] = []
    for path in files:
        findings.extend(check_file(path, cache))
    unique = {(f.rule, f.file, f.line, f.message): f for f in findings}
    ordered = sorted(unique.values(), key=lambda f: (f.file, f.line))
    for finding in ordered:
        finding.emit()
    _lib.finish(ordered)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
