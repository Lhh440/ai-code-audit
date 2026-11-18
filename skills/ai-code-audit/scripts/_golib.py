"""Shared helpers for the Go probes.

Go has no stdlib parser here, so imports, package symbols and function bodies are
read with narrow regexes plus a brace counter. Module resolution follows go.mod:
a package is only resolvable if it is stdlib, inside the module path, or listed
in `require`.
"""

from __future__ import annotations

import os
import re

from _lib import Finding, is_vendored, rel, root, skipped  # noqa: F401

STDLIB = {
    "archive/tar", "archive/zip", "bufio", "bytes", "cmp", "compress/gzip",
    "container/heap", "container/list", "context", "crypto/aes", "crypto/hmac",
    "crypto/rand", "crypto/sha256", "crypto/sha512", "crypto/tls", "database/sql",
    "embed", "encoding/base64", "encoding/binary", "encoding/csv", "encoding/gob",
    "encoding/hex", "encoding/json", "encoding/xml", "errors", "flag", "fmt",
    "go/ast", "go/parser", "go/token", "hash", "hash/crc32", "html", "html/template",
    "io", "io/fs", "io/ioutil", "log", "log/slog", "maps", "math", "math/big",
    "math/rand", "mime", "mime/multipart", "net", "net/http", "net/http/httptest",
    "net/url", "os", "os/exec", "os/signal", "os/user", "path", "path/filepath",
    "reflect", "regexp", "runtime", "slices", "sort", "strconv", "strings",
    "sync", "sync/atomic", "syscall", "testing", "text/template", "time", "unicode",
    "unicode/utf8", "unsafe",
}

IMPORT_LINE = re.compile(r'^import\s+(?:(\w+|\.|_)\s+)?["`]([^"`]+)["`]', re.M)
IMPORT_BLOCK = re.compile(r"^import\s*\(\s*\n(.*?)^\)", re.M | re.S)
BLOCK_LINE = re.compile(r'^\s*(?:(\w+|\.|_)\s+)?["`]([^"`]+)["`]', re.M)

SYMBOL = re.compile(
    r"^(?:func\s+(?:\([^)]*\)\s*)?([A-Z]\w*)|type\s+([A-Z]\w*)|(?:var|const)\s+([A-Z]\w*))",
    re.M,
)


def go_files(include_tests: bool = True) -> list[str]:
    explicit = os.environ.get("AUDIT_FILES", "").strip()
    if explicit:
        return [p for p in explicit.splitlines() if p.endswith(".go") and os.path.isfile(p)]
    base = root()
    out: list[str] = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(
            d for d in dirnames
            if d not in {"vendor", "testdata", "node_modules", ".git", "third_party"}
            and not d.startswith(".")
        )
        for name in sorted(filenames):
            if not name.endswith(".go"):
                continue
            full = os.path.join(dirpath, name)
            if is_vendored(full):
                continue
            if not include_tests and name.endswith("_test.go"):
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


def imports(source: str) -> list[tuple[int, str, str | None]]:
    """(line, import path, alias) for every import, single and in blocks."""
    found: list[tuple[int, str, str | None]] = []
    for match in IMPORT_LINE.finditer(source):
        line = source.count("\n", 0, match.start()) + 1
        found.append((line, match.group(2), match.group(1)))
    for block in IMPORT_BLOCK.finditer(source):
        base_line = source.count("\n", 0, block.start(1)) + 1
        for inner in BLOCK_LINE.finditer(block.group(1)):
            found.append((base_line + inner.group(0).count("\n"), inner.group(2), inner.group(1)))
    return sorted(set(found), key=lambda item: item[0])


def module_path() -> str:
    path = os.path.join(root(), "go.mod")
    if not os.path.isfile(path):
        return ""
    match = re.search(r"(?m)^module\s+(\S+)", read(path))
    return match.group(1).strip('"') if match else ""


def required_modules() -> set[str]:
    path = os.path.join(root(), "go.mod")
    if not os.path.isfile(path):
        return set()
    names: set[str] = set()
    for match in re.finditer(r"(?m)^\s*(?:require\s+)?(\S+)\s+v\d", read(path)):
        names.add(match.group(1))
    return names


def resolve_import(spec: str) -> str | None:
    """Directory the import path maps to, or None."""
    if spec in STDLIB:
        return spec
    module = module_path()
    if module and (spec == module or spec.startswith(module + "/")):
        relative = spec[len(module):].lstrip("/")
        target = os.path.join(root(), relative)
        return target if os.path.isdir(target) else None
    return None


def required_by_prefix(spec: str, required: set[str]) -> str | None:
    best = None
    for name in required:
        if spec == name or spec.startswith(name + "/"):
            if best is None or len(name) > len(best):
                best = name
    return best


def package_symbols() -> dict[str, set[str]]:
    """Directory -> exported identifiers declared in that package."""
    index: dict[str, set[str]] = {}
    for path in go_files():
        directory = os.path.dirname(os.path.abspath(path))
        names = index.setdefault(directory, set())
        for match in SYMBOL.finditer(read(path)):
            names.add(next(g for g in match.groups() if g))
    return index


def package_name(directory: str) -> str:
    for name in sorted(os.listdir(directory)) if os.path.isdir(directory) else []:
        if name.endswith(".go") and not name.endswith("_test.go"):
            match = re.search(r"(?m)^package\s+(\w+)", read(os.path.join(directory, name)))
            if match:
                return match.group(1)
    return os.path.basename(directory)


def funcs(source: str) -> list[tuple[str, int, str]]:
    """(name, line, body) for top-level function declarations."""
    out: list[tuple[str, int, str]] = []
    for match in re.finditer(r"(?m)^func\s+(?:\([^)]*\)\s*)?(\w+)\s*\(", source):
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
        if body.count("\n") >= 2:
            out.append((match.group(1), source.count("\n", 0, match.start()) + 1, body))
    return out
