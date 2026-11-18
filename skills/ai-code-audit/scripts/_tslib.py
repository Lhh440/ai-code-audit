"""Shared helpers for the TypeScript probes.

TypeScript has no stdlib parser in Python, so imports and exports are read with
deliberately narrow regexes plus a brace counter. Narrow beats clever here: every
pattern below matches a real syntactic form, and anything unmatched is ignored
rather than guessed.
"""

from __future__ import annotations

import os
import re

from _lib import Finding, is_test_file, is_vendored, rel, root, skipped  # noqa: F401

SOURCE_EXTS = (".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs")
INDEX_FILES = tuple("index" + ext for ext in SOURCE_EXTS)

NODE_BUILTINS = {
    "assert", "async_hooks", "buffer", "child_process", "cluster", "console",
    "crypto", "dgram", "diagnostics_channel", "dns", "domain", "events", "fs",
    "http", "http2", "https", "inspector", "module", "net", "os", "path",
    "perf_hooks", "process", "punycode", "querystring", "readline", "repl",
    "stream", "string_decoder", "timers", "tls", "trace_events", "tty", "url",
    "util", "v8", "vm", "wasi", "worker_threads", "zlib", "test",
}

# import ... from 'x' | import 'x' | import('x') | require('x') | export ... from 'x'
SPEC_PATTERNS = (
    re.compile(r"""^\s*import\s+(?:[\w*{}\s,$]+?\s+from\s+)?['"]([^'"]+)['"]""", re.M),
    re.compile(r"""^\s*export\s+(?:[\w*{}\s,$]+?\s+from\s+)['"]([^'"]+)['"]""", re.M),
    re.compile(r"""\brequire\(\s*['"]([^'"]+)['"]\s*\)"""),
    re.compile(r"""\bimport\(\s*['"]([^'"]+)['"]\s*\)"""),
)

EXPORT_PATTERNS = (
    re.compile(r"^\s*export\s+(?:default\s+)?(?:async\s+)?(?:function|class|const|let|var)\s+(\w+)", re.M),
    re.compile(r"^\s*export\s+(?:interface|type|enum)\s+(\w+)", re.M),
    re.compile(r"^\s*export\s*\{([^}]*)\}", re.M),
)

TEST_PATTERNS = (
    re.compile(r"\.(test|spec)\.[cm]?[jt]sx?$"),
    re.compile(r"(^|/)__tests__/"),
)


def is_ts_test(path: str) -> bool:
    if is_test_file(path):
        return True
    return any(p.search(path) for p in TEST_PATTERNS)


def ts_files() -> list[str]:
    explicit = os.environ.get("AUDIT_FILES", "").strip()
    if explicit:
        return [p for p in explicit.splitlines() if p.endswith(SOURCE_EXTS) and os.path.isfile(p)]
    base = root()
    out: list[str] = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(
            d for d in dirnames if d not in {"node_modules", "dist", "build", ".git", "coverage"}
            and not d.startswith(".")
        )
        for name in sorted(filenames):
            if name.endswith(SOURCE_EXTS) and not name.endswith(".d.ts"):
                full = os.path.join(dirpath, name)
                if not is_vendored(full):
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


def specs(source: str) -> list[tuple[int, str]]:
    """(line, specifier) for every import-like reference."""
    found: list[tuple[int, str]] = []
    for pattern in SPEC_PATTERNS:
        for match in pattern.finditer(source):
            line = source.count("\n", 0, match.start(1)) + 1
            found.append((line, match.group(1)))
    return sorted(set(found))


def resolve_relative(spec: str, importer: str) -> str | None:
    base = os.path.dirname(importer)
    target = os.path.normpath(os.path.join(base, spec))
    if os.path.isfile(target):
        return target
    stem, ext = os.path.splitext(target)
    candidates = [target + e for e in SOURCE_EXTS]
    if ext in (".js", ".jsx"):
        candidates += [stem + e for e in (".ts", ".tsx")]
    candidates += [os.path.join(target, index) for index in INDEX_FILES]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return None


def package_name(spec: str) -> str:
    parts = spec.split("/")
    return "/".join(parts[:2]) if spec.startswith("@") else parts[0]


def declared_dependencies() -> set[str]:
    import json

    names: set[str] = set()
    for manifest in ("package.json",):
        path = os.path.join(root(), manifest)
        if not os.path.isfile(path):
            continue
        try:
            data = json.loads(read(path) or "{}")
        except ValueError:
            continue
        if not isinstance(data, dict):
            continue
        for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
            section = data.get(key)
            if isinstance(section, dict):
                names.update(section)
    return names


def has_node_modules(spec: str) -> bool:
    return os.path.isdir(os.path.join(root(), "node_modules", package_name(spec)))


def exported_names(source: str) -> tuple[set[str], bool]:
    """Exported identifiers and whether a default export exists."""
    names: set[str] = set()
    has_default = bool(re.search(r"^\s*export\s+default\b", strip_comments(source), re.M))
    for pattern in EXPORT_PATTERNS[:2]:
        names.update(pattern.findall(source))
    for block in EXPORT_PATTERNS[2].findall(source):
        for piece in block.split(","):
            piece = piece.strip()
            if not piece:
                continue
            if piece.startswith("type "):
                piece = piece[5:].strip()
            if not piece:
                continue
            parts = piece.split(" as ")
            names.add(parts[-1].strip())
    if re.search(r"^\s*export\s+default\s+(\w+)", source, re.M):
        has_default = True
    return names, has_default


def function_bodies(source: str) -> list[tuple[str, int, str]]:
    """(name, line, body) for function declarations and arrow-function consts."""
    out: list[tuple[str, int, str]] = []
    pattern = re.compile(
        r"(?:^|\n)\s*(?:export\s+)?(?:async\s+)?(?:function\s+(\w+)|(?:const|let)\s+(\w+)\s*=\s*(?:async\s*)?\()"
    )
    for match in pattern.finditer(source):
        name = match.group(1) or match.group(2)
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
        body = source[open_brace + 1 : end]
        line = source.count("\n", 0, match.start()) + 1
        if body.count("\n") >= 2:
            out.append((name, line, body))
    return out
