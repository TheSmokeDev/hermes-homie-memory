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


def test_a_long_log_does_not_outrank_the_note_that_answers(tmp_path: Path) -> None:
    """The defect this scorer shipped with: raw term COUNT meant the biggest
    file won every query. An append-only ops log that mentions a term in
    passing hundreds of times outscored the short note actually about it — on
    a real vault, by 6305 to nothing. Length normalization plus term-frequency
    saturation is what keeps the answer on top.
    """

    _write(
        tmp_path / "_ops" / "history.md",
        "# Operations History\n\n" + ("ran the taskchad sync job. " * 400),
    )
    _write(
        tmp_path / "concepts" / "TASKCHAD-OFFER-LADDER.md",
        "# TaskChad Offer Ladder\n\nThe taskchad offer ladder is locked: "
        "chat, voice, website, employee.",
    )

    results = VaultIndex(tmp_path).search("taskchad offer ladder", limit=5)

    assert results[0].rel_path == "concepts/TASKCHAD-OFFER-LADDER.md"


def test_repeated_mentions_saturate(tmp_path: Path) -> None:
    """The 400th mention must be worth almost nothing more than the 20th —
    otherwise length normalization alone is still gameable by repetition."""

    _write(tmp_path / "twenty.md", "# Twenty\n\n" + ("alpha filler. " * 20))
    _write(tmp_path / "many.md", "# Many\n\n" + ("alpha filler. " * 400))

    scores = {r.rel_path: r.score for r in VaultIndex(tmp_path).search("alpha", limit=5)}

    assert scores["many.md"] < scores["twenty.md"] * 2
