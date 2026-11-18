#!/usr/bin/env python3
"""Regex scan for AI-slop tells in TypeScript.

No stdlib TS parser exists, so these are narrow line patterns against real
syntax forms. Every rule names what it cannot tell apart, and the severity
reflects that.

Usage: slop_scan_ts.sh [paths...]
"""

from __future__ import annotations

import difflib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _lib  # noqa: E402
import _tslib  # noqa: E402

SECRET_NAME = re.compile(r"(?i)(api[_-]?key|secret|token|passw|credential)\s*[:=]\s*['\"]([^'\"]{16,})['\"]")
NEAR_MISS_RATIO = 0.82

# (rule, severity, pattern, message, flags)
RULES = [
    ("ts-nocheck", "MAJOR", re.compile(r"//\s*@ts-nocheck"),
     "whole file opted out of type checking", ()),
    ("ts-ignore", "MINOR", re.compile(r"//\s*@ts-ignore\b"),
     "`@ts-ignore` hides the error even after it is fixed", ()),
    ("ts-expect-error-bare", "NIT", re.compile(r"//\s*@ts-expect-error\s*$"),
     "`@ts-expect-error` without an explanation", ()),
    ("any-type", "MINOR", re.compile(r"(?::\s*any\b|\bas\s+any\b|<any>)"),
     "`any` disables checking at this seam", ()),
    ("loose-equality", "MINOR", re.compile(r"[^=!<>]==(?!=)\s*(?!null|undefined)"),
     "`==` coerces; `===` unless null/undefined is intended", ()),
    ("innerhtml", "MAJOR", re.compile(r"\.innerHTML\s*="),
     "`innerHTML` parses untrusted markup; check for a sanitizer", ()),
    ("dangerous-html", "MINOR", re.compile(r"dangerouslySetInnerHTML"),
     "raw HTML injection point in JSX", ()),
    ("eval", "MINOR", re.compile(r"(?<![\w.])eval\s*\(|new\s+Function\s*\("),
     "eval/Function on a non-literal", ()),
    ("json-parse-unguarded", "MINOR", re.compile(r"JSON\.parse\("),
     "unguarded `JSON.parse` throws on any malformed input", ()),
    ("empty-catch", "MAJOR", re.compile(r"catch\s*(?:\([^)]*\))?\s*\{\s*\}"),
     "exception swallowed; caller cannot tell failure from success", ()),
    ("console-in-catch", "MINOR", re.compile(r"catch\s*(?:\([^)]*\))?\s*\{\s*console\."),
     "`catch` only logs; the error path still returns whatever is next", ()),
    ("fetch-no-signal", "MAJOR", re.compile(r"\bfetch\s*\("),
     "`fetch` has no timeout without a signal", ("notest", "sig")),
    ("shell-true", "MAJOR", re.compile(r"shell\s*:\s*true"),
     "`shell: true` with an interpolated command allows injection", ()),
    ("nonnull-env", "MINOR", re.compile(r"process\.env\.\w+!"),
     "`process.env.X!` lies when the var is unset", ()),
    ("console-log", "NIT", re.compile(r"(?<![\w.])console\.(log|debug)\("),
     "`console.log` left in library code", ("notest",)),
    ("sort-no-comparator", "MINOR", re.compile(r"\.sort\(\s*\)"),
     "default sort is lexicographic; numbers sort wrong", ()),
    ("parseint-no-radix", "NIT", re.compile(r"parseInt\(\s*[^,)]+\)"),
     "`parseInt` without a radix", ()),
    ("stub-throw", "MINOR", re.compile(r"throw new Error\(\s*['\"](?:TODO|not implemented|unimplemented)", re.I),
     "stub shipped as if complete", ()),
    ("todo", "MINOR", re.compile(r"(?://|/\*)\s*(TODO|FIXME|XXX)"),
     "unfinished marker left in code", ()),
    ("eslint-disable-bare", "NIT", re.compile(r"eslint-disable(?!-next-line\s+\S|\s+\S)"),
     "disable comment without a rule name", ()),
    ("settimeout-string", "MINOR", re.compile(r"setTimeout\(\s*['\"]"),
     "string argument to setTimeout is eval'd", ()),
    ("return-await", "NIT", re.compile(r"return\s+await\b"),
     "redundant await before return", ()),
    ("loose-array-copy", "NIT", re.compile(r"JSON\.parse\(JSON\.stringify\("),
     "deep clone via JSON loses Date/Map/undefined", ()),
]

MAX_LINES = 200


USAGE = """
Regex rules for AI-slop tells in TypeScript.

usage: slop-scan-ts [-h] [paths...]

Without paths, scans $AUDIT_ROOT (default: the directory the wrapper was run in).

Reads: .ts/.tsx files. Writes: nothing.
Findings: 23 regex rules; `fetch-no-signal` is a 6-line window heuristic.

Exit: 0 even with findings; findings go to stdout as JSON lines.
"""

def near_miss(source: str, path: str) -> list[_lib.Finding]:
    findings: list[_lib.Finding] = []
    bodies = _tslib.function_bodies(source)
    if len(bodies) < 2:
        return findings
    for i in range(len(bodies)):
        for j in range(i + 1, len(bodies)):
            name_a, line_a, body_a = bodies[i]
            name_b, line_b, body_b = bodies[j]
            ratio = difflib.SequenceMatcher(None, body_a, body_b).ratio()
            if ratio < NEAR_MISS_RATIO:
                continue
            if ratio == 1.0:
                note = f"`{name_a}` and `{name_b}` are identical copies"
            else:
                note = f"`{name_a}` and `{name_b}` are near-identical ({ratio:.0%})"
                if re.search(rf"\b{re.escape(name_a)}\b", body_b):
                    note += "; check for a stale self-reference"
            findings.append(_lib.Finding(
                rule="near-miss-copy", severity="MINOR", file=_lib.rel(path),
                line=line_b, message=note, evidence=f"function {name_b}", confidence="medium",
            ))
    return findings


def scan(path: str) -> list[_lib.Finding]:
    findings: list[_lib.Finding] = []
    source = _tslib.read(path)
    if not source:
        _lib.skipped(_lib.rel(path), "unreadable")
        return findings
    cleaned = _tslib.strip_comments(source)
    in_test = _tslib.is_ts_test(path)
    lines = source.splitlines()

    for rule, severity, pattern, message, flags in RULES:
        if "notest" in flags and in_test:
            continue
        for match in pattern.finditer(source):
            line = source.count("\n", 0, match.start()) + 1
            if "sig" in flags:
                window = cleaned.splitlines()[line - 1 : line + 6]
                if any("signal" in text or "AbortController" in text for text in window):
                    continue
            findings.append(_lib.Finding(
                rule=rule, severity=severity, file=_lib.rel(path), line=line,
                message=message, evidence=lines[line - 1].strip()[:160] if line <= len(lines) else "",
                confidence="low" if severity == "NIT" else "medium",
            ))

    for match in SECRET_NAME.finditer(source):
        line = source.count("\n", 0, match.start()) + 1
        findings.append(_lib.Finding(
            rule="hardcoded-secret", severity="MINOR", file=_lib.rel(path), line=line,
            message=f"`{match.group(1)}` looks hardcoded", evidence=match.group(0)[:80],
        ))

    findings.extend(near_miss(cleaned, path))

    if len(lines) > MAX_LINES and not in_test:
        findings.append(_lib.Finding(
            rule="long-file", severity="NIT", file=_lib.rel(path), line=1,
            message=f"{len(lines)} lines in one module; AI output tends to sprawl",
            evidence=f"{len(lines)} lines", confidence="low",
        ))

    seen: set[tuple[str, int]] = set()
    unique: list[_lib.Finding] = []
    for finding in findings:
        key = (finding.rule, finding.line)
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)
    return unique


def main(argv: list[str]) -> int:
    _lib.usage(argv, USAGE)
    files = argv or _tslib.ts_files()
    findings: list[_lib.Finding] = []
    for path in files:
        findings.extend(scan(path))
    findings.sort(key=lambda f: (f.file, f.line))
    for finding in findings:
        finding.emit()
    _lib.finish(findings)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
