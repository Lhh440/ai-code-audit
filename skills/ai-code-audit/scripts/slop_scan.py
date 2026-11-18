#!/usr/bin/env python3
"""AST scan for AI-slop tells in Python. Stdlib only fallback for ast-grep.

Each rule is (id, severity, matcher). Matchers are tiny functions over one AST
node, so adding a rule is three lines and no grammar work.

Usage: slop_scan.sh [paths...]
Env:   AUDIT_ROOT
"""

from __future__ import annotations

import ast
import difflib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _lib  # noqa: E402

SECRET_NAME = re.compile(r"(?i)(api_?key|secret|token|passw|credential)")
SECRET_ASSIGN = re.compile(r"^(sk-|ghp_|xox[bap]-|AKIA)[\w-]{8,}$")
HTTP_CALLS = {"get", "post", "put", "patch", "delete", "request", "head", "stream"}
HTTP_MODULES = {"requests", "httpx", "aiohttp", "urllib3"}


class Ctx:
    def __init__(self) -> None:
        self.http_aliases: set[str] = set()
        self.in_test = False


USAGE = """
AST rules for AI-slop tells in Python.

usage: slop-scan [-h] [paths...]

Without paths, scans $AUDIT_ROOT (default: the directory the wrapper was run in).

Reads: .py files. Writes: nothing.
Findings: 17 AST + 3 line rules, mostly MINOR/NIT; blank_ok on GIL-free claims.

Exit: 0 even with findings; findings go to stdout as JSON lines.
"""

def walk(tree: ast.AST):
    return ast.walk(tree)


def is_true(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value is True


def is_none(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value is None


def names_in(node: ast.AST) -> set[str]:
    return {n.id for n in walk(node) if isinstance(n, ast.Name)}


# --- rule matchers ---------------------------------------------------------

def bare_except(node, ctx):
    if isinstance(node, ast.ExceptHandler) and node.type is None:
        return "bare `except:` catches KeyboardInterrupt and SystemExit too", "MAJOR"
    return None


def swallowed_exception(node, ctx):
    if not isinstance(node, ast.ExceptHandler):
        return None
    body = node.body
    silent = all(
        isinstance(s, ast.Pass)
        or (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))
        for s in body
    )
    if silent and node.type is not None:
        return "exception swallowed silently; caller cannot tell failure from success", "MAJOR"
    return None


def broad_except(node, ctx):
    if isinstance(node, ast.ExceptHandler) and node.type is not None:
        caught = node.type
        if isinstance(caught, ast.Name) and caught.id in {"Exception", "BaseException"}:
            has_raise = any(isinstance(n, ast.Raise) for n in walk_body(node))
            if not has_raise:
                return "catches `Exception` and never re-raises", "MINOR"
    return None


def walk_body(handler):
    for stmt in handler.body:
        yield from walk(stmt)


def tautological_assert(node, ctx):
    if not isinstance(node, ast.Assert):
        return None
    test = node.test
    if is_true(test):
        return "`assert True` proves nothing", "MINOR"
    if isinstance(test, ast.Compare) and len(test.comparators) == 1:
        left, right = test.left, test.comparators[0]
        if ast.dump(left) == ast.dump(right):
            return "asserted value compared to itself", "MINOR"
    return None


def bool_compare(node, ctx):
    if isinstance(node, ast.Compare):
        for op, comp in zip(node.ops, node.comparators):
            if isinstance(op, (ast.Is, ast.IsNot)):
                continue
            if is_true(comp) or is_none(comp):
                word = "True" if is_true(comp) else "None"
                return f"compares against `{word}` with == instead of `is`", "NIT"
    return None


def mutable_default(node, ctx):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        for default in node.args.defaults + [d for d in node.args.kw_defaults if d]:
            if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                return "mutable default argument is shared across calls", "MAJOR"
    return None


def eval_exec(node, ctx):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id in {"eval", "exec"}:
            return f"`{node.func.id}()` on a non-literal", "MINOR"
    return None


def shell_true(node, ctx):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr in {"run", "Popen", "call", "check_output"}:
            for kw in node.keywords:
                if kw.arg == "shell" and is_true(kw.value):
                    return "`shell=True` without quoting the command", "MAJOR"
    return None


def os_system(node, ctx):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr == "system" and isinstance(node.func.value, ast.Name):
            if node.func.value.id == "os":
                return "`os.system` hides failures; prefer subprocess.run(check=True)", "MINOR"
    return None


def open_without_encoding(node, ctx):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id == "open":
            if any(kw.arg == "encoding" for kw in node.keywords):
                return None
            binary = any(
                kw.arg == "mode" and isinstance(kw.value, ast.Constant)
                and "b" in str(kw.value.value)
                for kw in node.keywords
            )
            if not binary:
                return "`open()` without `encoding=` depends on the host locale", "MINOR"
    return None


def http_no_timeout(node, ctx):
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    is_http = False
    if isinstance(func, ast.Attribute) and func.attr in HTTP_CALLS:
        base = func.value
        if isinstance(base, ast.Name) and base.id in ctx.http_aliases:
            is_http = True
        if isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name):
            if base.value.id in HTTP_MODULES:
                is_http = True
        if isinstance(base, ast.Name) and base.id in HTTP_MODULES:
            is_http = True
    if not is_http:
        return None
    has_timeout = any(kw.arg == "timeout" for kw in node.keywords)
    if not has_timeout and not ctx.in_test:
        return "HTTP call without a timeout will hang forever", "MAJOR"
    return None


def yaml_load(node, ctx):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr == "load" and isinstance(node.func.value, ast.Name):
            if node.func.value.id in {"yaml", "ruamel"}:
                if not any(kw.arg in {"Loader", "loader"} for kw in node.keywords):
                    return "`yaml.load()` without SafeLoader", "MAJOR"
    return None


def sql_fstring(node, ctx):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr in {"execute", "executemany", "text"}:
            arg = node.args[0] if node.args else None
            if isinstance(arg, ast.JoinedStr):
                if not any(isinstance(v, ast.FormattedValue) for v in walk(arg) if isinstance(v, ast.FormattedValue)):
                    return None
                return "f-string SQL: values are interpolated, not bound", "MAJOR"
    return None


def utcnow(node, ctx):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr == "utcnow":
            return "`utcnow()` returns a naive datetime", "MINOR"
    return None


def hardcoded_secret(node, ctx):
    if isinstance(node, (ast.Assign, ast.AnnAssign)):
        value = getattr(node, "value", None)
        if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
            return None
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name) and SECRET_NAME.search(target.id):
                if len(value.value) >= 16 and not value.value.startswith(("${", "os.environ")):
                    return f"`{target.id}` looks like a hardcoded credential", "MINOR"
    return None


def print_in_library(node, ctx):
    if ctx.in_test:
        return None
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id == "print":
            return "`print()` in library code", "NIT"
    return None


def todo_comment(node, ctx):
    return None  # handled by line scan


def raises_exception_in_test(node, ctx):
    if not ctx.in_test:
        return None
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr != "raises" or not node.args:
            return None
        caught = node.args[0]
        if isinstance(caught, ast.Name) and caught.id in {"Exception", "BaseException"}:
            return "`pytest.raises(Exception)` accepts any failure, including a typo", "MINOR"
    return None


def type_ignore(node, ctx):
    return None  # handled by line scan


RULES = [
    ("bare-except", bare_except),
    ("swallowed-exception", swallowed_exception),
    ("broad-except", broad_except),
    ("tautological-assert", tautological_assert),
    ("bool-identity", bool_compare),
    ("mutable-default", mutable_default),
    ("eval-exec", eval_exec),
    ("shell-true", shell_true),
    ("os-system", os_system),
    ("open-without-encoding", open_without_encoding),
    ("http-no-timeout", http_no_timeout),
    ("yaml-unsafe-load", yaml_load),
    ("sql-interpolation", sql_fstring),
    ("utcnow", utcnow),
    ("hardcoded-secret", hardcoded_secret),
    ("print-in-library", print_in_library),
    ("raises-exception", raises_exception_in_test),
]

LINE_RULES = [
    (re.compile(r"#\s*(TODO|FIXME|XXX)\b"), "todo-comment", "MINOR", "unfinished marker left in code"),
    (re.compile(r"#\s*type:\s*ignore\b"), "type-ignore", "NIT", "type: ignore hides a real mismatch"),
    (re.compile(r"#\s*noqa\b(?!:)"), "bare-noqa", "NIT", "noqa without a rule code"),
]

MAX_LINES = 120


NEAR_MISS_RATIO = 0.82


def near_miss(tree: ast.AST, source: str, path: str) -> list[_lib.Finding]:
    """Two functions that are copies except for one stale identifier."""
    findings: list[_lib.Finding] = []
    funcs = [
        n for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and len(n.body) >= 3
    ]
    if len(funcs) < 2:
        return findings
    bodies = []
    for node in funcs:
        try:
            bodies.append("\n".join(ast.unparse(stmt) for stmt in node.body))
        except Exception:  # noqa: BLE001
            bodies.append("")
    for i in range(len(funcs)):
        for j in range(i + 1, len(funcs)):
            if not bodies[i] or not bodies[j]:
                continue
            ratio = difflib.SequenceMatcher(None, bodies[i], bodies[j]).ratio()
            if ratio < NEAR_MISS_RATIO:
                continue
            other = funcs[j].name
            stale = [
                n.id for n in walk(funcs[i])
                if isinstance(n, ast.Name) and n.id == funcs[i].name and funcs[i].name != other
            ]
            if ratio == 1.0:
                note = f"`{funcs[i].name}` and `{funcs[j].name}` are identical copies"
            else:
                note = f"`{funcs[i].name}` and `{funcs[j].name}` are near-identical ({ratio:.0%})"
            if stale and ratio < 1.0:
                note += "; check for a stale self-reference"
            findings.append(_lib.Finding(
                rule="near-miss-copy", severity="MINOR", file=_lib.rel(path),
                line=funcs[j].lineno, message=note,
                evidence=_snippet(source, funcs[j].lineno), confidence="medium",
            ))
    return findings


def scan(path: str) -> list[_lib.Finding]:
    findings: list[_lib.Finding] = []
    try:
        source = open(path, encoding="utf-8", errors="replace").read()
        tree = ast.parse(source)
    except (OSError, SyntaxError):
        _lib.skipped(_lib.rel(path), "unreadable or invalid syntax")
        return findings

    ctx = Ctx()
    ctx.in_test = _lib.is_test_file(path)
    for node in walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in HTTP_MODULES:
                    ctx.http_aliases.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] in HTTP_MODULES:
                for alias in node.names:
                    ctx.http_aliases.add(alias.asname or alias.name)

    for rule_id, matcher in RULES:
        for node in walk(tree):
            result = matcher(node, ctx)
            if result:
                message, severity = result
                findings.append(_lib.Finding(
                    rule=rule_id, severity=severity, file=_lib.rel(path),
                    line=getattr(node, "lineno", 0), message=message,
                    evidence=_snippet(source, getattr(node, "lineno", 0)),
                ))

    for lineno, line in enumerate(source.splitlines(), 1):
        for pattern, rule_id, severity, message in LINE_RULES:
            if pattern.search(line):
                findings.append(_lib.Finding(
                    rule=rule_id, severity=severity, file=_lib.rel(path), line=lineno,
                    message=message, evidence=line.strip()[:160],
                ))

    findings.extend(near_miss(tree, source, path))

    total = len(source.splitlines())
    if total > MAX_LINES and not ctx.in_test:
        findings.append(_lib.Finding(
            rule="long-file", severity="NIT", file=_lib.rel(path), line=1,
            message=f"{total} lines in one module; AI output tends to sprawl",
            evidence=f"{total} lines", confidence="low",
        ))
    return findings


def _snippet(source: str, lineno: int) -> str:
    lines = source.splitlines()
    if 1 <= lineno <= len(lines):
        return lines[lineno - 1].strip()[:200]
    return ""


def main(argv: list[str]) -> int:
    _lib.usage(argv, USAGE)
    files = argv or _lib.target_files()
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
