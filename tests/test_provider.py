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


def test_initialize_honors_hermes_home_kwarg(tmp_path: Path, monkeypatch) -> None:
    """Hermes passes hermes_home to initialize(); native config must resolve there."""
    vault = tmp_path / "vault"
    _write(vault / "MEMORY.md", "# Memory\n\nprofile scoped recall")
    profile_home = tmp_path / "profile-home"
    profile_home.mkdir()
    (profile_home / "hermes-homie-memory.json").write_text(
        json.dumps({"vault_path": str(vault), "max_prefetch_chars": 640}),
        encoding="utf-8",
    )
    # Ensure ambient resolution cannot accidentally supply the vault.
    monkeypatch.delenv("HERMES_HOMIE_MEMORY_VAULT_PATH", raising=False)
    monkeypatch.delenv("HOMIE_VAULT_DIR", raising=False)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "wrong-home"))

    provider = HomieMemoryProvider()
    provider.initialize("session-1", platform="cli", hermes_home=str(profile_home))

    payload = json.loads(provider.handle_tool_call("homie_memory_status", {}))
    assert payload["success"] is True
    assert payload["documents"] == 1


def test_on_session_switch_updates_session_id(tmp_path: Path) -> None:
    _write(tmp_path / "MEMORY.md", "# Memory\n\nstable index")
    provider = HomieMemoryProvider(HomieMemoryConfig(vault_path=tmp_path))
    provider.initialize("session-1", platform="cli")

    provider.on_session_switch("session-2", parent_session_id="session-1", reset=True)

    assert provider._session_id == "session-2"
    payload = json.loads(provider.handle_tool_call("homie_memory_status", {}))
    assert payload["success"] is True


def test_signatures_match_memory_provider_contract() -> None:
    """Lock our overrides to the upstream keyword-only shapes (drift alarm)."""
    import inspect

    prefetch = inspect.signature(HomieMemoryProvider.prefetch)
    assert prefetch.parameters["session_id"].kind is inspect.Parameter.KEYWORD_ONLY

    sync_turn = inspect.signature(HomieMemoryProvider.sync_turn)
    assert list(sync_turn.parameters) == [
        "self", "user_content", "assistant_content", "session_id", "messages",
    ]
    assert sync_turn.parameters["session_id"].kind is inspect.Parameter.KEYWORD_ONLY
    assert sync_turn.parameters["messages"].kind is inspect.Parameter.KEYWORD_ONLY

    switch = inspect.signature(HomieMemoryProvider.on_session_switch)
    for kw in ("parent_session_id", "reset", "rewound"):
        assert switch.parameters[kw].kind is inspect.Parameter.KEYWORD_ONLY


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
