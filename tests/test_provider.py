from __future__ import annotations

import json
from pathlib import Path

from config import HomieMemoryConfig
from provider import HomieMemoryProvider


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_provider_tools_return_json(tmp_path: Path) -> None:
    _write(tmp_path / "MEMORY.md", "# Memory\n\nHermes should recall Homie vault decisions.")
    provider = HomieMemoryProvider(HomieMemoryConfig(vault_path=tmp_path))
    provider.initialize("session-1", platform="cli")

    payload = json.loads(provider.handle_tool_call("homie_memory_search", {"query": "Hermes Homie"}))

    assert payload["success"] is True
    assert payload["read_only"] is True
    assert payload["results"][0]["path"] == "MEMORY.md"


def test_prefetch_returns_capped_context(tmp_path: Path) -> None:
    _write(tmp_path / "MEMORY.md", "# Memory\n\n" + ("Homie memory recall " * 80))
    provider = HomieMemoryProvider(HomieMemoryConfig(vault_path=tmp_path, max_prefetch_chars=700))
    provider.initialize("session-1", platform="cli")

    context = provider.prefetch("Homie recall")

    assert context.startswith("## Homie Memory Recall")
    assert len(context) < 850


def test_missing_vault_status_is_json_error(tmp_path: Path) -> None:
    provider = HomieMemoryProvider(HomieMemoryConfig(vault_path=tmp_path / "missing"))
    provider.initialize("session-1", platform="cli")

    payload = json.loads(provider.handle_tool_call("homie_memory_status", {}))

    assert payload["success"] is False
    assert payload["read_only"] is True


def test_sync_turn_is_read_only_noop(tmp_path: Path) -> None:
    _write(tmp_path / "MEMORY.md", "# Memory\n\nbefore")
    provider = HomieMemoryProvider(HomieMemoryConfig(vault_path=tmp_path))
    provider.initialize("session-1", platform="cli")

    provider.sync_turn("user", "assistant", session_id="session-1", messages=[])

    assert (tmp_path / "MEMORY.md").read_text(encoding="utf-8") == "# Memory\n\nbefore"


def test_register_entrypoint_collects_provider() -> None:
    import importlib.util

    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "_test_homie_plugin",
        root / "__init__.py",
        submodule_search_locations=[str(root)],
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class Collector:
        provider = None

        def register_memory_provider(self, provider):
            self.provider = provider

    collector = Collector()
    module.register(collector)

    assert collector.provider is not None
    assert collector.provider.name == "hermes-homie-memory"
