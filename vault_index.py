"""Read-only Markdown vault indexing for Homie memory recall."""

from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


TOKEN_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_-]*")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)")

SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".obsidian",
    ".trash",
    ".DS_Store",
    "__pycache__",
    "_state",
}


class VaultIndexError(ValueError):
    """Raised when a vault path or query option is unsafe or invalid."""


@dataclass(frozen=True)
class VaultDocument:
    rel_path: str
    title: str
    headings: tuple[str, ...]
    links: tuple[str, ...]
    content: str
    modified_at: float


@dataclass(frozen=True)
class SearchResult:
    rel_path: str
    title: str
    score: float
    snippet: str
    headings: tuple[str, ...]


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


def _safe_relative_filter(path_prefix: str | None) -> str:
    if not path_prefix:
        return ""
    normalized = path_prefix.replace("\\", "/").strip("/")
    if not normalized:
        return ""
    candidate = Path(normalized)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise VaultIndexError("path_prefix must be a safe relative path")
    return normalized


def _iter_markdown_files(root: Path, *, max_files: int) -> Iterable[Path]:
    count = 0
    for path in sorted(root.rglob("*.md")):
        if count >= max_files:
            break
        try:
            if path.is_symlink() or any(part in SKIP_DIRS for part in path.relative_to(root).parts):
                continue
        except ValueError:
            continue
        count += 1
        yield path


def _title_from_content(path: Path, content: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip() or path.stem
    return path.stem.replace("-", " ").replace("_", " ").strip() or path.name


def _snippet(content: str, query_terms: set[str], *, max_chars: int = 360) -> str:
    compact = re.sub(r"\s+", " ", content).strip()
    if not compact:
        return ""
    lower = compact.lower()
    first_hit = min((lower.find(term) for term in query_terms if term and lower.find(term) >= 0), default=0)
    start = max(0, first_hit - max_chars // 3)
    end = min(len(compact), start + max_chars)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(compact) else ""
    return f"{prefix}{compact[start:end].strip()}{suffix}"


class VaultIndex:
    """Small in-memory index over a plain Markdown Homie vault."""

    def __init__(self, root: str | Path, *, max_files: int = 1000):
        self.root = self._resolve_root(root)
        self.max_files = max_files
        self.documents: list[VaultDocument] = []
        self.indexed_at = 0.0
        self.refresh()

    @staticmethod
    def _resolve_root(root: str | Path) -> Path:
        resolved = Path(root).expanduser().resolve()
        if not resolved.exists():
            raise VaultIndexError(f"vault path does not exist: {resolved}")
        if not resolved.is_dir():
            raise VaultIndexError(f"vault path is not a directory: {resolved}")
        return resolved

    def refresh(self) -> None:
        docs: list[VaultDocument] = []
        for path in _iter_markdown_files(self.root, max_files=self.max_files):
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
                rel_path = path.relative_to(self.root).as_posix()
                headings = tuple(match.group(2).strip() for match in HEADING_RE.finditer(content))
                links = tuple(sorted(set(link.strip() for link in WIKILINK_RE.findall(content) if link.strip())))
                docs.append(
                    VaultDocument(
                        rel_path=rel_path,
                        title=_title_from_content(path, content),
                        headings=headings,
                        links=links,
                        content=content,
                        modified_at=path.stat().st_mtime,
                    )
                )
            except OSError:
                continue
        self.documents = docs
        self.indexed_at = time.time()

    def status(self) -> dict[str, object]:
        total_chars = sum(len(doc.content) for doc in self.documents)
        return {
            "vault_path": str(self.root),
            "documents": len(self.documents),
            "total_chars": total_chars,
            "indexed_at": self.indexed_at,
            "read_only": True,
        }

    def search(self, query: str, *, limit: int = 5, path_prefix: str | None = None) -> list[SearchResult]:
        query = (query or "").strip()
        if not query:
            raise VaultIndexError("query is required")
        limit = max(1, min(int(limit or 5), 20))
        prefix = _safe_relative_filter(path_prefix)
        query_terms = set(_tokens(query))
        if not query_terms:
            raise VaultIndexError("query must contain searchable words")

        results: list[SearchResult] = []
        phrase = query.lower()
        doc_count = max(1, len(self.documents))
        document_frequency = {
            term: sum(1 for doc in self.documents if term in set(_tokens(doc.title + "\n" + doc.content)))
            for term in query_terms
        }

        for doc in self.documents:
            if prefix and not doc.rel_path.startswith(prefix):
                continue
            title_tokens = _tokens(doc.title)
            heading_tokens = _tokens(" ".join(doc.headings))
            body_tokens = _tokens(doc.content)
            body_counts = {term: body_tokens.count(term) for term in query_terms}

            score = 0.0
            for term in query_terms:
                idf = math.log((doc_count + 1) / (1 + document_frequency.get(term, 0))) + 1
                score += body_counts[term] * idf
                if term in title_tokens:
                    score += 8 * idf
                if term in heading_tokens:
                    score += 4 * idf
            if phrase and phrase in doc.content.lower():
                score += 12.0
            if phrase and phrase in doc.title.lower():
                score += 16.0
            if score <= 0:
                continue
            results.append(
                SearchResult(
                    rel_path=doc.rel_path,
                    title=doc.title,
                    score=round(score, 4),
                    snippet=_snippet(doc.content, query_terms),
                    headings=doc.headings[:5],
                )
            )

        results.sort(key=lambda item: (-item.score, item.rel_path))
        return results[:limit]

    def context(self, query: str, *, max_chars: int = 2500, limit: int = 5) -> str:
        results = self.search(query, limit=limit)
        blocks: list[str] = []
        remaining = max(500, max_chars)
        for result in results:
            block = f"- {result.title} ({result.rel_path}, score {result.score}): {result.snippet}"
            if len(block) > remaining:
                block = block[: max(0, remaining - 3)].rstrip() + "..."
            blocks.append(block)
            remaining -= len(block) + 1
            if remaining <= 0:
                break
        return "\n".join(blocks)
