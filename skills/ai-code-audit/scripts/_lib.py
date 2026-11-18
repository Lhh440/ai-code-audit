"""Shared helpers for ai-code-audit probes.

Stdlib only. Every probe prints findings as one JSON object per line to stdout
and a human summary to stderr, so agents can parse one and humans read the other.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import asdict, dataclass

SEVERITIES = ("BLOCKER", "MAJOR", "MINOR", "NIT")

SKIP_SUFFIXES = (
    ".min.js", ".min.css", ".lock", ".svg", ".snap", ".map",
    ".png", ".jpg", ".gif", ".pdf", ".zip", ".whl",
)

VENDOR_DIRS = {
    "node_modules", ".venv", "venv", "env", "site-packages", "vendor",
    "third_party", "dist", "build", ".tox", ".mypy_cache", ".ruff_cache",
    "__pycache__", "migrations",
}

GENERATED_HINTS = ("# generated", "# auto-generated", "@generated", "do not edit")


@dataclass
class Finding:
    rule: str
    severity: str
    file: str
    line: int
    message: str
    evidence: str
    confidence: str = "high"

    def emit(self) -> None:
        print(json.dumps(asdict(self), ensure_ascii=False))


def root() -> str:
    return os.environ.get("AUDIT_ROOT") or os.getcwd()


def rel(path: str, base: str | None = None) -> str:
    base = base or root()
    try:
        return os.path.relpath(path, base)
    except ValueError:
        return path


def usage(argv: list[str], text: str) -> None:
    """Print usage and exit when -h/--help is asked for.

    Every probe is meant to be readable before it is trusted: the help text
    states what is read, what is written, and what it costs.
    """
    if any(arg in ("-h", "--help", "help") for arg in argv):
        print(text.strip())
        raise SystemExit(0)


def skipped(name: str, reason: str) -> None:
    print(f"skipped: {name} ({reason})", file=sys.stderr)


def require(tool: str) -> bool:
    if shutil.which(tool):
        return True
    skipped(tool, "not installed")
    return False


def is_vendored(path: str) -> bool:
    parts = set(path.replace(os.sep, "/").split("/"))
    return bool(parts & VENDOR_DIRS)


def is_generated(path: str, head: str) -> bool:
    if path.endswith(SKIP_SUFFIXES):
        return True
    lowered = head[:400].lower()
    return path.endswith((".pyi",)) or any(h in lowered for h in GENERATED_HINTS)


def target_files(include_tests: bool = True) -> list[str]:
    """Files under the audit root, honouring AUDIT_FILES when set."""
    explicit = os.environ.get("AUDIT_FILES", "").strip()
    if explicit:
        return [p for p in explicit.splitlines() if p and os.path.isfile(p)]

    base = root()
    out: list[str] = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if d not in VENDOR_DIRS and not d.startswith("."))
        for name in sorted(filenames):
            if not name.endswith(".py"):
                continue
            full = os.path.join(dirpath, name)
            if is_vendored(full):
                continue
            if not include_tests and is_test_file(full):
                continue
            out.append(full)
    return out


def is_test_file(path: str) -> bool:
    name = os.path.basename(path)
    normalized = "/" + path.replace(os.sep, "/")
    return (
        name.startswith("test_")
        or name.startswith("tests")
        or name == "test.py"
        or name.endswith("_test.py")
        or name == "conftest.py"
        or "/tests/" in normalized
        or "/test/" in normalized
        or "/test_" in normalized
    )


def finish(findings: list[Finding]) -> None:
    counts = {s: sum(1 for f in findings if f.severity == s) for s in SEVERITIES}
    parts = [f"{n} {s.lower()}" for s, n in counts.items() if n]
    print(
        f"{len(findings)} finding(s)" + (": " + ", ".join(parts) if parts else ""),
        file=sys.stderr,
    )
