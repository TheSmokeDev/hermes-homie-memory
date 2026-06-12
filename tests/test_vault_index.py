from __future__ import annotations

from pathlib import Path

import pytest

from vault_index import VaultIndex, VaultIndexError


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_search_ranks_title_and_content(tmp_path: Path) -> None:
    _write(tmp_path / "MEMORY.md", "# Long-Term Memory\n\nThe operator chose lane-first runtime selection.")
    _write(tmp_path / "daily" / "2026-06-12.md", "# Daily Log\n\nRandom notes.")

    index = VaultIndex(tmp_path)
    results = index.search("lane runtime", limit=3)

    assert results
    assert results[0].rel_path == "MEMORY.md"
    assert "lane-first" in results[0].snippet


def test_context_respects_character_cap(tmp_path: Path) -> None:
    _write(tmp_path / "MEMORY.md", "# Memory\n\n" + ("alpha beta gamma " * 200))

    index = VaultIndex(tmp_path)
    context = index.context("alpha", max_chars=520)

    assert len(context) <= 520
    assert "Memory" in context


def test_path_prefix_must_be_relative(tmp_path: Path) -> None:
    _write(tmp_path / "MEMORY.md", "# Memory\n\nhello")

    index = VaultIndex(tmp_path)

    with pytest.raises(VaultIndexError):
        index.search("hello", path_prefix="../")


def test_symlinked_files_are_skipped(tmp_path: Path) -> None:
    target = tmp_path / "outside.md"
    target.write_text("# Secret\n\nshould not index", encoding="utf-8")
    link = tmp_path / "linked.md"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation unavailable")

    index = VaultIndex(tmp_path)

    assert all(doc.rel_path != "linked.md" for doc in index.documents)
