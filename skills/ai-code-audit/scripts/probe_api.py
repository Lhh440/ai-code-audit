#!/usr/bin/env python3
"""Detect hallucinated symbols and call signatures against local modules.

Checks, for locally defined modules only (no imports of user code):
  1. `from app.x import y` where `y` is not defined in `app/x.py`
  2. `mod.attr` where `attr` is not defined in the imported local module
  3. calls passing keyword arguments the local function does not accept

Usage: probe_api.sh [paths...]
Env:   AUDIT_ROOT
"""

from __future__ import annotations

import ast
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _lib  # noqa: E402


class ModuleDefs:
    __slots__ = ("path", "names", "signatures")

    def __init__(self, path: str) -> None:
        self.path = path
        self.names: set[str] = set()
        self.signatures: dict[str, set[str]] = {}

    def accepts(self, func: str) -> set[str] | None:
        return self.signatures.get(func)


USAGE = """
Hallucinated symbols and keyword arguments against local modules.

usage: probe-api [-h] [paths...]

Without paths, scans $AUDIT_ROOT (default: the directory the wrapper was run in).

Reads: local .py modules plus the files given.
Writes: nothing. Shells out: no.
Findings: hallucinated-symbol/-attribute/-module BLOCKER, unsupported-keyword MAJOR.

Exit: 0 even with findings; findings go to stdout as JSON lines.
"""

def local_modules() -> dict[str, ModuleDefs]:
    """Map dotted module paths to their definitions for files under the root."""
    base = _lib.root()
    modules: dict[str, ModuleDefs] = {}
    for path in _lib.target_files():
        relpath = os.path.relpath(path, base)[: -len(".py")]
        dotted = relpath.replace(os.sep, ".")
        if dotted.endswith(".__init__"):
            dotted = dotted[: -len(".__init__")]
        modules[dotted] = index(path, dotted)
        modules.setdefault(dotted.split(".")[-1], modules[dotted])
    return modules


def index(path: str, dotted: str) -> ModuleDefs:
    entry = ModuleDefs(path)
    try:
        tree = ast.parse(open(path, encoding="utf-8", errors="replace").read())
    except (OSError, SyntaxError):
        return entry

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            entry.names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    entry.names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            entry.names.add(node.target.id)
        elif isinstance(node, ast.Import):
            entry.names.update(a.asname or a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            entry.names.update(a.asname or a.name for a in node.names)
        elif isinstance(node, ast.ClassDef):
            pass

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            params: set[str] = set()
            args = node.args
            for group in (args.posonlyargs, args.args, args.kwonlyargs):
                params.update(a.arg for a in group)
            if args.vararg:
                params.add("*" + args.vararg.arg)
            if args.kwarg:
                params.add("**" + args.kwarg.arg)
            entry.signatures[node.name] = params

    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    try:
                        entry.names.update(ast.literal_eval(node.value))
                    except ValueError:
                        pass
    return entry


def submodule_of(parent: ModuleDefs, name: str) -> ModuleDefs | None:
    """Resolve `from pkg import name` where name is a submodule file next to pkg."""
    base = os.path.dirname(os.path.abspath(parent.path))
    for candidate in (os.path.join(base, name + ".py"), os.path.join(base, name, "__init__.py")):
        if os.path.isfile(candidate):
            return index(candidate, name)
    return None


def package_candidates(module: str, modules: dict[str, ModuleDefs]) -> list[ModuleDefs]:
    """All modules whose dotted path equals or ends in `module` (handles repo-root offsets)."""
    found = []
    direct = modules.get(module)
    if direct is not None:
        found.append(direct)
    suffix = "." + module
    for key, value in modules.items():
        if key.endswith(suffix) and value not in found:
            found.append(value)
    return found


def resolve_dotted(
    module: str, modules: dict[str, ModuleDefs]
) -> tuple[list[ModuleDefs] | None, str | None]:
    """Resolve a dotted module path, longest resolvable prefix first.

    Returns (modules, None) when nothing local matches at all, (None, path)
    when a local prefix exists but a segment does not, and (modules, None)
    on success.
    """
    parts = module.split(".")
    for i in range(len(parts), 0, -1):
        current = package_candidates(".".join(parts[:i]), modules)
        if not current:
            continue
        for index, segment in enumerate(parts[i:], start=i):
            nxt: list[ModuleDefs] = []
            for candidate in current:
                sub = submodule_of(candidate, segment)
                if sub is not None:
                    nxt.append(sub)
            if not nxt:
                return None, ".".join(parts[: index + 1])
            current = nxt
        return current, None
    return None, None


def resolve(node: ast.AST, modules: dict[str, ModuleDefs]) -> ModuleDefs | None:
    if isinstance(node, ast.Name):
        return modules.get(node.id)
    if isinstance(node, ast.Attribute):
        inner = resolve(node.value, modules)
        if inner is None:
            return None
        dotted = qualified(node)
        return modules.get(dotted)
    return None


def qualified(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:  # noqa: BLE001
        return "<expr>"


def check_file(path: str, modules: dict[str, ModuleDefs]) -> list[_lib.Finding]:
    findings: list[_lib.Finding] = []
    try:
        tree = ast.parse(open(path, encoding="utf-8", errors="replace").read())
    except (OSError, SyntaxError):
        return findings

    local_aliases: dict[str, ModuleDefs] = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                resolved, missing = resolve_dotted(alias.name, modules)
                if resolved:
                    local_aliases[alias.asname or alias.name.split(".")[0]] = resolved[-1]
                elif missing:
                    findings.append(_lib.Finding(
                        rule="hallucinated-module", severity="BLOCKER", file=_lib.rel(path),
                        line=node.lineno, message=f"module '{missing}' does not exist",
                        evidence=qualified(node), confidence="high",
                    ))

        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            candidates, missing = resolve_dotted(node.module, modules)
            if candidates is None:
                if missing:
                    findings.append(_lib.Finding(
                        rule="hallucinated-module", severity="BLOCKER", file=_lib.rel(path),
                        line=node.lineno, message=f"module '{missing}' does not exist",
                        evidence=qualified(node), confidence="high",
                    ))
                continue
            target = candidates[0]
            defined: set[str] = set()
            subs: dict[str, ModuleDefs] = {}
            for candidate in candidates:
                defined |= candidate.names
                for alias in node.names:
                    sub = submodule_of(candidate, alias.name)
                    if sub is not None:
                        subs[alias.name] = sub
                        local_aliases.setdefault(alias.asname or alias.name, sub)
            for alias in node.names:
                if alias.name == "*" or alias.name in defined or alias.name in subs:
                    continue
                findings.append(_lib.Finding(
                    rule="hallucinated-symbol", severity="BLOCKER", file=_lib.rel(path),
                    line=node.lineno,
                    message=f"'{alias.name}' is imported from '{node.module}' but not defined there",
                    evidence=qualified(node), confidence="high",
                ))

        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            target = local_aliases.get(node.value.id)
            if target is None or node.attr.startswith("__"):
                continue
            if node.attr not in target.names:
                findings.append(_lib.Finding(
                    rule="hallucinated-attribute", severity="BLOCKER", file=_lib.rel(path),
                    line=node.lineno,
                    message=f"'{node.value.id}.{node.attr}' does not exist in {_lib.rel(target.path)}",
                    evidence=qualified(node), confidence="high",
                ))

        elif isinstance(node, ast.Call):
            target, func_name = match_call(node, local_aliases, modules)
            if target is None or func_name is None:
                continue
            accepted = target.accepts(func_name)
            if accepted is None or "**" + "" in accepted or any(p.startswith("**") for p in accepted):
                continue
            for keyword in node.keywords:
                if keyword.arg and keyword.arg not in accepted:
                    findings.append(_lib.Finding(
                        rule="unsupported-keyword", severity="MAJOR", file=_lib.rel(path),
                        line=node.lineno,
                        message=(
                            f"'{func_name}()' has no parameter '{keyword.arg}' "
                            f"(accepts: {', '.join(sorted(accepted)) or 'none'})"
                        ),
                        evidence=qualified(node)[:200], confidence="high",
                    ))
    return findings


def match_call(
    node: ast.Call, aliases: dict[str, ModuleDefs], modules: dict[str, ModuleDefs]
) -> tuple[ModuleDefs | None, str | None]:
    func = node.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        target = aliases.get(func.value.id)
        if target is not None:
            return target, func.attr
        return None, None
    if isinstance(func, ast.Name):
        # A module is registered under its dotted path and its short name; dedupe.
        seen: dict[int, ModuleDefs] = {}
        for module in modules.values():
            if func.id in module.signatures:
                seen[id(module)] = module
        if len(seen) == 1:
            return next(iter(seen.values())), func.id
    return None, None


def main(argv: list[str]) -> int:
    _lib.usage(argv, USAGE)
    modules = local_modules()
    if not modules:
        _lib.skipped("probe_api", "no local modules")
        return 0
    files = argv or _lib.target_files()
    findings: list[_lib.Finding] = []
    for path in files:
        findings.extend(check_file(path, modules))
    unique = {(f.rule, f.file, f.line, f.message): f for f in findings}
    ordered = sorted(unique.values(), key=lambda f: (f.file, f.line))
    for finding in ordered:
        finding.emit()
    _lib.finish(ordered)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
