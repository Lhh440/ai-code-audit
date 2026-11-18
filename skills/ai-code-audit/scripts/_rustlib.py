"""Shared helpers for the Rust probes.

No Rust parser is available to Python. `use` paths are resolved against the
module tree so only genuinely missing paths are reported.
"""

from __future__ import annotations

import os
import re

from _lib import Finding, is_vendored, rel, root, skipped  # noqa: F401

CRATES_BUILTIN = {"std", "core", "alloc", "proc_macro", "test"}

USE_LINE = re.compile(r"(?m)^\s*(?:pub\s+)?use\s+([^;]+);")
EXTERN_CRATE = re.compile(r"(?m)^\s*extern\s+crate\s+(\w+)")
PUB_ITEM = re.compile(
    r"(?m)^\s*pub(?:\([^)]*\))?\s+(?:async\s+)?(?:unsafe\s+)?"
    r"(?:fn|struct|enum|trait|type|const|static|mod|union)\s+(\w+)"
)
ANY_ITEM = re.compile(
    r"(?m)^\s*(?:(?:pub(?:\([^)]*\))?)\s+)?(?:async\s+)?(?:unsafe\s+)?"
    r"(?:fn|struct|enum|trait|type|const|static|mod|union)\s+(\w+)"
)


def rust_files(include_tests: bool = True) -> list[str]:
    explicit = os.environ.get("AUDIT_FILES", "").strip()
    if explicit:
        return [p for p in explicit.splitlines() if p.endswith(".rs") and os.path.isfile(p)]
    base = root()
    out: list[str] = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(
            d for d in dirnames if d not in {"target", "tests", "benches", "node_modules", ".git"}
            and not d.startswith(".")
        )
        for name in sorted(filenames):
            if not name.endswith(".rs"):
                continue
            full = os.path.join(dirpath, name)
            if is_vendored(full):
                continue
            out.append(full)
    return out


def read(path: str) -> str:
    try:
        return open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return ""


def strip_comments(source: str) -> str:
    """Blank comments but keep newlines, so line numbers stay aligned."""
    source = re.sub(
        r"/\*.*?\*/",
        lambda match: re.sub(r"[^\n]", " ", match.group(0)),
        source,
        flags=re.S,
    )
    return re.sub(r"(?m)^\s*//.*$", lambda match: " " * len(match.group(0)), source)


def cargo_manifest() -> str:
    for name in ("Cargo.toml",):
        path = os.path.join(root(), name)
        if os.path.isfile(path):
            return read(path)
    return ""


def declared_crates() -> set[str]:
    """Dependency names, with dashes folded to underscores as crates expect."""
    deps: set[str] = set()
    section = ""
    for line in cargo_manifest().splitlines():
        header = re.match(r"\s*\[([^\]]+)\]", line)
        if header:
            section = header.group(1).strip()
            continue
        if not section.endswith("dependencies"):
            continue
        match = re.match(r"\s*([A-Za-z0-9_-]+)\s*=", line)
        if match:
            deps.add(match.group(1).replace("-", "_"))
    return deps


def workspace_root() -> str | None:
    """Directory containing src/ next to the manifest, if any."""
    base = root()
    if os.path.isdir(os.path.join(base, "src")):
        return base
    for candidate in ("crates", "packages"):
        wrote = False
        for parent in (os.path.join(base, candidate),):
            if os.path.isdir(parent):
                for child in sorted(os.listdir(parent)):
                    if os.path.isdir(os.path.join(parent, child, "src")):
                        return os.path.join(parent, child)
                wrote = True
        if wrote:
            break
    return None


def resolve_module(segments: list[str], importer: str) -> str | None:
    """Resolve a module path relative to the crate root or the importer."""
    base = workspace_root() or root()
    src = os.path.join(base, "src")
    if not os.path.isdir(src):
        return None
    joined = os.path.join(src, *segments)
    candidates = [joined + ".rs", os.path.join(joined, "mod.rs")]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return None


def module_of(path: str) -> str | None:
    return path


def pub_names(path: str) -> set[str]:
    return set(PUB_ITEM.findall(read(path)))


def all_names(path: str) -> set[str]:
    return set(ANY_ITEM.findall(read(path)))


def resolves_submodule(path: str, name: str) -> bool:
    stem = path[:-3] if path.endswith(".rs") else path
    directory = stem if os.path.basename(path) == "mod.rs" else stem
    for candidate in (os.path.join(directory, name + ".rs"), os.path.join(directory, name, "mod.rs")):
        if os.path.isfile(candidate):
            return True
    return False


def funcs(source: str) -> list[tuple[str, int, str]]:
    out: list[tuple[str, int, str]] = []
    for match in re.finditer(r"(?m)^\s*(?:pub\s+)?(?:async\s+)?fn\s+(\w+)\s*[<(]", source):
        open_brace = source.find("{", match.end())
        if open_brace < 0:
            continue
        depth = 0
        end = -1
        for index in range(open_brace, len(source)):
            char = source[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    end = index
                    break
        if end < 0:
            continue
        body = source[open_brace + 1:end]
        if body.count("\n") >= 2:
            out.append((match.group(1), source.count("\n", 0, match.start()) + 1, body))
    return out
