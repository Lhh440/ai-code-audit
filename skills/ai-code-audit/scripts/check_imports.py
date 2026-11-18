#!/usr/bin/env python3
"""Find imports that cannot be resolved: hallucinated modules and undeclared deps.

Usage: check_imports.sh [paths...]
Env:   AUDIT_ROOT, AUDIT_FILES
Exit:  0 always (findings are data, not failure)
"""

from __future__ import annotations

import ast
import importlib.metadata as md
import importlib.util
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _lib  # noqa: E402

# sys.stdlib_module_names exists on 3.10+. Keep a coarse fallback for older hosts.
STDLIB_FALLBACK = {
    "abc", "argparse", "ast", "asyncio", "base64", "collections", "contextlib",
    "csv", "dataclasses", "datetime", "decimal", "enum", "functools", "glob",
    "gzip", "hashlib", "heapq", "hmac", "html", "http", "importlib", "inspect",
    "io", "itertools", "json", "logging", "math", "operator", "os", "pathlib",
    "pickle", "platform", "pprint", "queue", "random", "re", "secrets",
    "shutil", "signal", "socket", "sqlite3", "ssl", "statistics", "string",
    "struct", "subprocess", "sys", "tempfile", "textwrap", "threading", "time",
    "tomllib", "traceback", "types", "typing", "unittest", "urllib", "uuid",
    "warnings", "weakref", "xml", "zipfile", "zlib",
}

TEST_ONLY = {"pytest", "hypothesis", "freezegun", "responses", "faker", "mypy", "ruff"}

PYPROJECT = ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "requirements-dev.txt")


def stdlib_names() -> set[str]:
    return set(getattr(sys, "stdlib_module_names", STDLIB_FALLBACK))


def declared_deps() -> set[str]:
    """Top-level names mentioned in dependency manifests (coarse, good enough)."""
    names: set[str] = set()
    for manifest in PYPROJECT:
        path = os.path.join(_lib.root(), manifest)
        if not os.path.isfile(path):
            continue
        try:
            text = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for match in re.finditer(r"[\"']([A-Za-z0-9_.\-]+)", text):
            names.add(canonical(match.group(1)))
    return names


def canonical(name: str) -> str:
    return name.lower().replace("-", "_").split(".")[0]


def installed_toplevels() -> set[str]:
    tops: set[str] = set()
    try:
        for top, dists in md.packages_distributions().items():
            if dists:
                tops.add(top.lower())
    except Exception:  # noqa: BLE001 - metadata can be broken in odd envs
        pass
    return tops


def local_resolves(module: str) -> bool:
    """A local file or package, in the root or below it.

    Walking is deliberate: audits often start at a monorepo root while the
    package lives a few levels down.
    """
    base = _lib.root()
    relative = module.replace(".", os.sep)
    for candidate in (relative + ".py", relative):
        if os.path.exists(os.path.join(base, candidate)):
            return True
    for dirpath, dirnames, _ in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in _lib.VENDOR_DIRS]
        if os.path.isfile(os.path.join(dirpath, relative + ".py")):
            return True
        if os.path.isdir(os.path.join(dirpath, relative)):
            return True
    return False


def resolves_with_import(path: str, module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError, AttributeError):
        return False


def module_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Import):
        return None
    if isinstance(node, ast.ImportFrom):
        return node.module
    return None


def check_file(path: str, stdlib: set[str], installed: set[str], declared: set[str]) -> list[_lib.Finding]:
    findings: list[_lib.Finding] = []
    try:
        source = open(path, encoding="utf-8", errors="replace").read()
    except OSError as exc:
        _lib.skipped(path, str(exc))
        return findings
    try:
        tree = ast.parse(source)
    except SyntaxError:
        _lib.skipped(_lib.rel(path), "syntax error")
        return findings

    in_tests = _lib.is_test_file(path)
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue  # relative import, resolved by the package itself
            if node.module:
                names = [node.module]
        for module in names:
            top = canonical(module)
            line = node.lineno

            if top in stdlib or top in sys.builtin_module_names:
                continue
            if top in installed or local_resolves(module):
                if top not in declared and top not in installed:
                    continue
                if top in installed and top not in declared and top not in TEST_ONLY:
                    findings.append(_lib.Finding(
                        rule="undeclared-dependency", severity="MINOR", file=_lib.rel(path),
                        line=line, message=f"'{top}' is installed but not declared in any manifest",
                        evidence=ast.unparse(node) if hasattr(ast, "unparse") else module,
                    ))
                continue
            if in_tests and top in TEST_ONLY:
                continue

            if local_resolves(module) or resolves_with_import(path, module):
                continue
            severity = "MAJOR"
            findings.append(_lib.Finding(
                rule="unresolvable-import", severity=severity, file=_lib.rel(path), line=line,
                message=f"cannot resolve module '{module}' (not stdlib, local, or installed)",
                evidence=ast.unparse(node) if hasattr(ast, "unparse") else module,
                confidence="high",
            ))
    return findings


def main(argv: list[str]) -> int:
    files = argv or _lib.target_files()
    if not files:
        _lib.skipped("check_imports", "no Python files")
        return 0
    stdlib = stdlib_names()
    installed = installed_toplevels()
    declared = declared_deps()
    findings: list[_lib.Finding] = []
    for path in files:
        findings.extend(check_file(path, stdlib, installed, declared))
    for finding in findings:
        finding.emit()
    _lib.finish(findings)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
