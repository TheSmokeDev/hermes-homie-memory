from __future__ import annotations

import json
from pathlib import Path

from config import ENV_VAULT_PATH, HomieMemoryConfig, resolve_config, save_native_config


def test_env_vault_path(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv(ENV_VAULT_PATH, str(tmp_path))
    cfg = resolve_config()

    assert isinstance(cfg, HomieMemoryConfig)
    assert cfg.vault_path == tmp_path
    assert cfg.available is True


def test_save_native_config_writes_json(tmp_path: Path) -> None:
    path = save_native_config({"vault_path": str(tmp_path), "max_prefetch_chars": "1200"}, tmp_path)

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["vault_path"] == str(tmp_path)
    assert data["max_prefetch_chars"] == "1200"
