#!/usr/bin/env python3
"""Regex scan for AI-slop tells in Go.

No Go parser is available to Python, so these are narrow patterns against real
syntax. Rules that cannot see context carry a lower severity or confidence.

Usage: slop_scan_go.sh [paths...]
"""

from __future__ import annotations

import difflib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _golib  # noqa: E402
import _lib  # noqa: E402

NEAR_MISS_RATIO = 0.82

RULES = [
    ("empty-err-check", "MAJOR", re.compile(r"if\s+[^;{\n]*;\s*err\s*!=\s*nil\s*\{\s*\}|if\s+err\s*!=\s*nil\s*\{\s*\}"),
     "error checked and then ignored"),
    ("nil-err-return", "MAJOR", re.compile(r"if\s+err\s*!=\s*nil\s*\{\s*return\s+nil\s*\}"),
     "returns nil instead of the error it just checked"),
    ("discarded-error", "MINOR", re.compile(r"^\s*\w+,\s*_\s*:?=\s*"),
     "second return value discarded; usually the error", ("lowconf",)),
    ("blank-err-assign", "MINOR", re.compile(r"\b_\s*=\s*\w*[Ee]rr\w*"),
     "error assigned to `_`"),
    ("panic", "MINOR", re.compile(r"^\s*panic\("),
     "`panic` in library code; caller cannot recover without defer"),
    ("log-fatal", "MAJOR", re.compile(r"^\s*log\.(Fatal|Fatalf|Panic)\("),
     "`log.Fatal` calls os.Exit and skips deferred cleanup"),
    ("os-exit", "MAJOR", re.compile(r"\bos\.Exit\("),
     "`os.Exit` skips deferred cleanup"),
    ("http-default-client", "MAJOR", re.compile(r"\bhttp\.(Get|Post|Head|PostForm)\("),
     "package-level http call uses a client with no timeout"),
    ("sql-format", "MAJOR", re.compile(r"\.(Query|QueryRow|Exec)\(\s*fmt\.Sprintf"),
     "values formatted into SQL instead of bound"),
    ("context-background", "MINOR", re.compile(r"\bcontext\.Background\(\)"),
     "Background loses the caller's cancellation"),
    ("time-sleep", "MINOR", re.compile(r"\btime\.Sleep\("),
     "`time.Sleep` is untestable without a clock seam", ("notest",)),
    ("time-since", "NIT", re.compile(r"time\.Now\(\)\.Sub\("),
     "`time.Since` is the same thing, shorter"),
    ("ioutil", "NIT", re.compile(r"\bioutil\.\w+"),
     "ioutil is deprecated in favour of os/io"),
    ("any-interface", "NIT", re.compile(r"\b(interface\{\}|any)\b"),
     "untyped parameter; check whether a constraint fits"),
    ("unsafe", "MINOR", re.compile(r"\bunsafe\.(Pointer|Sizeof|Alignof)"),
     "unsafe escapes the type system"),
    ("println-lib", "NIT", re.compile(r"\bfmt\.Print(ln|f)?\("),
     "`fmt.Print*` in library code", ("notest",)),
    ("todo", "MINOR", re.compile(r"(?://|/\*)\s*(TODO|FIXME|XXX)"),
     "unfinished marker left in code"),
    ("nolint-bare", "NIT", re.compile(r"//\s*nolint\s*$"),
     "`nolint` without a linter name"),
    ("chdir", "NIT", re.compile(r"\bos\.Chdir\("),
     "`os.Chdir` is process-global and test-order dependent", ("notest",)),
    ("fmt-sprintf-error", "NIT", re.compile(r"errors\.New\(fmt\.Sprintf\("),
     "`fmt.Errorf` does the same thing"),
    ("stub-panic", "MINOR", re.compile(r"panic\(\"(TODO|not implemented|unimplemented)"),
     "stub shipped as complete"),
]

MAX_LINES = 200


USAGE = """
Regex rules for AI-slop tells in Go.

usage: slop-scan-go [-h] [paths...]

Without paths, scans $AUDIT_ROOT (default: the directory the wrapper was run in).

Reads: .go files. Writes: nothing.
Findings: 21 regex rules; `discarded-error` is low confidence by nature.

Exit: 0 even with findings; findings go to stdout as JSON lines.
"""

def near_miss(source: str, path: str) -> list[_lib.Finding]:
    findings: list[_lib.Finding] = []
    bodies = _golib.funcs(source)
    for i in range(len(bodies)):
        for j in range(i + 1, len(bodies)):
            name_a, _line_a, body_a = bodies[i]
            name_b, line_b, body_b = bodies[j]
            ratio = difflib.SequenceMatcher(None, body_a, body_b).ratio()
            if ratio < NEAR_MISS_RATIO:
                continue
            note = (f"`{name_a}` and `{name_b}` are identical copies" if ratio == 1.0
                    else f"`{name_a}` and `{name_b}` are near-identical ({ratio:.0%})")
            findings.append(_lib.Finding(
                rule="near-miss-copy", severity="MINOR", file=_lib.rel(path),
                line=line_b, message=note, evidence=f"func {name_b}", confidence="medium",
            ))
    return findings


def defer_in_loop(source: str, path: str) -> list[_lib.Finding]:
    findings: list[_lib.Finding] = []
    for match in re.finditer(r"(?m)^\s*for\s+.*\{", source):
        line_end = source.find("\n", match.end())
        line_end = len(source) if line_end < 0 else line_end
        open_brace = source.rfind("{", match.start(), line_end)
        if open_brace < 0:
            continue
        depth = 0
        end = -1
        for index in range(open_brace, len(source)):
            if source[index] == "{":
                depth += 1
            elif source[index] == "}":
                depth -= 1
                if depth == 0:
                    end = index
                    break
        if end < 0:
            continue
        body = source[match.end():end]
        for defer in re.finditer(r"(?m)^\s*defer\s+", body):
            line = source.count("\n", 0, match.end() + defer.start()) + 1
            findings.append(_lib.Finding(
                rule="defer-in-loop", severity="MINOR", file=_lib.rel(path), line=line,
                message="`defer` inside a loop runs at function exit, not iteration end",
                evidence=defer.group(0).strip(), confidence="high",
            ))
    return findings


def scan(path: str) -> list[_lib.Finding]:
    findings: list[_lib.Finding] = []
    source = _golib.read(path)
    if not source:
        _lib.skipped(_lib.rel(path), "unreadable")
        return findings
    cleaned = _golib.strip_comments(source)
    in_test = path.endswith("_test.go")
    lines = source.splitlines()

    for rule, severity, pattern, message, *flags in RULES:
        pattern = re.compile(pattern.pattern, pattern.flags | re.M)
        if flags and "notest" in flags[0] and in_test:
            continue
        haystack = source if rule.endswith("-comment") or rule == "todo" else cleaned
        for match in pattern.finditer(haystack):
            line = haystack.count("\n", 0, match.start()) + 1
            findings.append(_lib.Finding(
                rule=rule, severity=severity, file=_lib.rel(path), line=line, message=message,
                evidence=lines[line - 1].strip()[:160] if line <= len(lines) else "",
                confidence="low" if flags and "lowconf" in flags[0] else "medium",
            ))

    findings.extend(defer_in_loop(cleaned, path))
    findings.extend(near_miss(cleaned, path))

    if len(lines) > MAX_LINES and not in_test:
        findings.append(_lib.Finding(
            rule="long-file", severity="NIT", file=_lib.rel(path), line=1,
            message=f"{len(lines)} lines in one file; AI output tends to sprawl",
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
    files = argv or _golib.go_files()
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
