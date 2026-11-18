#!/usr/bin/env python3
"""Regex scan for AI-slop tells in Rust.

Clippy covers most of this when it is installed; these rules target what clippy
does not say about completeness and error handling.

Usage: slop_scan_rust.sh [paths...]
"""

from __future__ import annotations

import difflib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _lib  # noqa: E402
import _rustlib  # noqa: E402

NEAR_MISS_RATIO = 0.82

RULES = [
    ("todo-macro", "MAJOR", re.compile(r"\b(todo!|unimplemented!)\s*\("),
     "stub macro shipped as complete"),
    ("unwrap", "MINOR", re.compile(r"\.unwrap\(\)"),
     "`unwrap` panics with no context", ("notest",)),
    ("bare-expect", "MINOR", re.compile(r"\.expect\(\s*(\"\"|\)|\(\s*\))"),
     "`expect` with an empty message explains nothing", ("notest",)),
    ("discarded-result", "MINOR", re.compile(r"\blet\s+_\s*="),
     "`let _ =` drops a Result or must_use value"),
    ("ignore-attr", "MINOR", re.compile(r"#\[ignore\]"),
     "`#[ignore]` test does not run in CI"),
    ("allow-bare", "NIT", re.compile(r"#\[allow\([^)]*\)\]"),
     "allow attribute without a reason"),
    ("panic-macro", "MINOR", re.compile(r"\bpanic!\("),
     "`panic!` in library code"),
    ("process-exit", "MAJOR", re.compile(r"std::process::exit\(|\bprocess::exit\("),
     "process::exit skips destructors"),
    ("unsafe-block", "MINOR", re.compile(r"\bunsafe\s*\{"),
     "unsafe block; check for a SAFETY comment"),
    ("cast", "NIT", re.compile(r"\bas\s+(u8|u16|u32|u64|usize|i8|i16|i32|i64|isize|f32|f64)\b"),
     "`as` truncates silently; try_from is checked"),
    ("string-param", "MINOR", re.compile(r"fn\s+\w+\s*\([^)]*:\s*String\b"),
     "`String` parameter where `&str` would do"),
    ("vec-ref-param", "NIT", re.compile(r":\s*&Vec<"),
     "`&Vec<T>` parameter where `&[T]` would do"),
    ("string-param-ref", "NIT", re.compile(r":\s*&String\b"),
     "`&String` parameter where `&str` would do"),
    ("println-lib", "NIT", re.compile(r"\b(println!|print!)"),
     "`println!` in library code", ("notest",)),
    ("dbg-macro", "MINOR", re.compile(r"\bdbg!\("),
     "`dbg!` left in place"),
    ("unreachable-macro", "NIT", re.compile(r"\bunreachable!\("),
     "`unreachable!` is an unproven claim"),
    ("empty-match-arm", "MINOR", re.compile(r"_\s*=>\s*\{\s*\}"),
     "catch-all arm does nothing; the case is silently ignored"),
    ("todo-comment", "MINOR", re.compile(r"(?://|/\*)\s*(TODO|FIXME|XXX)"),
     "unfinished marker left in code"),
    ("shell-command", "MINOR", re.compile(r"Command::new\(\s*\"(sh|bash)\"\s*\)"),
     "shell invocation; the argument string is one injection away"),
    ("cloned-collect", "NIT", re.compile(r"\.iter\(\)\.cloned\(\)\.collect"),
     "`.iter().cloned().collect()` where `to_vec()` is plainer"),
    ("expect-unwrap-ish", "MINOR", re.compile(r"\.expect\(\s*\"(unwrap|error|failed)\""),
     "`expect` message restates the obvious"),
]

MAX_LINES = 200


def near_miss(source: str, path: str) -> list[_lib.Finding]:
    findings: list[_lib.Finding] = []
    bodies = _rustlib.funcs(source)
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
                line=line_b, message=note, evidence=f"fn {name_b}", confidence="medium",
            ))
    return findings


def unsafe_without_safety(source: str, path: str) -> list[_lib.Finding]:
    findings: list[_lib.Finding] = []
    lines = source.splitlines()
    for match in re.finditer(r"\bunsafe\s*\{", source):
        line = source.count("\n", 0, match.start()) + 1
        window = " ".join(lines[max(0, line - 3):line + 2]).lower()
        if "safety" in window:
            continue
        findings.append(_lib.Finding(
            rule="unsafe-no-safety-note", severity="MINOR", file=_lib.rel(path), line=line,
            message="unsafe block without a `// SAFETY:` note",
            evidence=lines[line - 1].strip()[:160] if line <= len(lines) else "",
        ))
    return findings


def scan(path: str) -> list[_lib.Finding]:
    findings: list[_lib.Finding] = []
    source = _rustlib.read(path)
    if not source:
        _lib.skipped(_lib.rel(path), "unreadable")
        return findings
    cleaned = _rustlib.strip_comments(source)
    in_test = "/tests/" in path.replace(os.sep, "/") or path.endswith("_test.rs")
    lines = source.splitlines()

    for rule, severity, pattern, message, *flags in RULES:
        pattern = re.compile(pattern.pattern, pattern.flags | re.M)
        if flags and "notest" in flags[0] and in_test:
            continue
        for match in pattern.finditer(cleaned):
            line = cleaned.count("\n", 0, match.start()) + 1
            findings.append(_lib.Finding(
                rule=rule, severity=severity, file=_lib.rel(path), line=line, message=message,
                evidence=lines[line - 1].strip()[:160] if line <= len(lines) else "",
                confidence="low" if severity == "NIT" else "medium",
            ))

    findings.extend(unsafe_without_safety(source, path))
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
    files = argv or _rustlib.rust_files()
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
