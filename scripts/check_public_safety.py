from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".md", ".py", ".toml", ".yaml", ".yml", ".txt", ".json"}
BLOCKED_PATH_PARTS = {".git", ".pytest_cache", "__pycache__", ".venv", "venv", ".mypy_cache"}
PATTERNS = [
    re.compile(r"C:\\Users\\Degen", re.IGNORECASE),
    re.compile("second" + r"-brain", re.IGNORECASE),
    re.compile("PRP" + r"s?/", re.IGNORECASE),
    re.compile(r"TRACKER\.md", re.IGNORECASE),
    re.compile(r"\." + r"env(?:\b|$)", re.IGNORECASE),
    re.compile(r"gho_[A-Za-z0-9_]+"),
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+", re.IGNORECASE),
]


def iter_text_files():
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in BLOCKED_PATH_PARTS for part in path.relative_to(ROOT).parts):
            continue
        if path.suffix.lower() in TEXT_SUFFIXES:
            yield path


def main() -> int:
    findings: list[str] = []
    for path in iter_text_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in PATTERNS:
            if pattern.search(text):
                findings.append(f"{path.relative_to(ROOT)} matches {pattern.pattern}")
    if findings:
        print("FAILED public-safety scan:")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print("PASSED public-safety scan")
    return 0


if __name__ == "__main__":
    sys.exit(main())
