"""Configuration helpers for the Hermes Homie memory provider."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


PROVIDER_NAME = "hermes-homie-memory"
CONFIG_BASENAME = "hermes-homie-memory.json"
ENV_VAULT_PATH = "HERMES_HOMIE_MEMORY_VAULT_PATH"
HOMIE_ENV_VAULT_PATH = "HOMIE_VAULT_DIR"


@dataclass(frozen=True)
class HomieMemoryConfig:
    """Resolved provider config."""

    vault_path: Path | None
    max_prefetch_chars: int = 2500
    max_tool_chars: int = 8000
    max_files: int = 1000

    @property
    def available(self) -> bool:
        return self.vault_path is not None and self.vault_path.is_dir()


def _get_hermes_home() -> Path:
    try:
        from hermes_constants import get_hermes_home

        return Path(get_hermes_home())
    except Exception:
        env = os.environ.get("HERMES_HOME")
        if env:
            return Path(env).expanduser()
        return Path.home() / ".hermes"


def _expand_path(value: str | os.PathLike[str] | None) -> Path | None:
    if not value:
        return None
    raw = os.path.expandvars(str(value)).strip()
    if not raw:
        return None
    return Path(raw).expanduser()


def _coerce_int(value: Any, default: int, *, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def _nested(mapping: Mapping[str, Any], *keys: str) -> Any:
    cur: Any = mapping
    for key in keys:
        if not isinstance(cur, Mapping) or key not in cur:
            return None
        cur = cur[key]
    return cur


def _load_hermes_config() -> dict[str, Any]:
    try:
        from hermes_cli.config import load_config

        loaded = load_config()
        return loaded if isinstance(loaded, dict) else {}
    except Exception:
        return {}


def _load_native_config(hermes_home: Path | None = None) -> dict[str, Any]:
    home = hermes_home or _get_hermes_home()
    path = home / CONFIG_BASENAME
    if not path.exists():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        return loaded if isinstance(loaded, dict) else {}
    except Exception:
        return {}


def resolve_config(overrides: Mapping[str, Any] | None = None) -> HomieMemoryConfig:
    """Resolve provider config without mutating disk."""
    overrides = overrides or {}
    hermes_home = _get_hermes_home()
    native = _load_native_config(hermes_home)
    hermes_config = _load_hermes_config()

    vault_value = (
        overrides.get("vault_path")
        or os.environ.get(ENV_VAULT_PATH)
        or os.environ.get(HOMIE_ENV_VAULT_PATH)
        or native.get("vault_path")
        or _nested(hermes_config, "hermes_homie_memory", "vault_path")
        or _nested(hermes_config, "memory", "hermes_homie_memory", "vault_path")
        or _nested(hermes_config, "memory", "hermes-homie-memory", "vault_path")
    )

    default_candidate = hermes_home / "vault" / "memory"
    vault_path = _expand_path(vault_value) or (default_candidate if default_candidate.is_dir() else None)

    max_prefetch_chars = _coerce_int(
        overrides.get("max_prefetch_chars")
        or native.get("max_prefetch_chars")
        or _nested(hermes_config, "hermes_homie_memory", "max_prefetch_chars"),
        2500,
        minimum=500,
        maximum=12000,
    )
    max_tool_chars = _coerce_int(
        overrides.get("max_tool_chars")
        or native.get("max_tool_chars")
        or _nested(hermes_config, "hermes_homie_memory", "max_tool_chars"),
        8000,
        minimum=1000,
        maximum=50000,
    )
    max_files = _coerce_int(
        overrides.get("max_files")
        or native.get("max_files")
        or _nested(hermes_config, "hermes_homie_memory", "max_files"),
        1000,
        minimum=10,
        maximum=10000,
    )

    return HomieMemoryConfig(
        vault_path=vault_path,
        max_prefetch_chars=max_prefetch_chars,
        max_tool_chars=max_tool_chars,
        max_files=max_files,
    )


def save_native_config(values: Mapping[str, Any], hermes_home: str | os.PathLike[str]) -> Path:
    """Write Hermes setup values to the provider's profile-local config file."""
    home = Path(hermes_home).expanduser()
    home.mkdir(parents=True, exist_ok=True)
    path = home / CONFIG_BASENAME

    existing: dict[str, Any] = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                existing = loaded
        except Exception:
            existing = {}

    existing.update({k: v for k, v in values.items() if v is not None})
    path.write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path
