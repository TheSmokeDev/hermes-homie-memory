"""Hermes MemoryProvider implementation for a read-only Homie vault."""

from __future__ import annotations

import json
import logging
from typing import Any

try:
    from agent.memory_provider import MemoryProvider
except Exception:  # pragma: no cover - local tests outside Hermes
    class MemoryProvider:  # type: ignore[no-redef]
        pass

try:
    from .config import HomieMemoryConfig, resolve_config, save_native_config
    from .vault_index import VaultIndex, VaultIndexError
except ImportError:  # pragma: no cover - direct import fallback for local tests
    from config import HomieMemoryConfig, resolve_config, save_native_config
    from vault_index import VaultIndex, VaultIndexError


logger = logging.getLogger(__name__)

SEARCH_SCHEMA = {
    "name": "homie_memory_search",
    "description": "Search the configured Homie Markdown vault. Read-only.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query."},
            "limit": {"type": "integer", "description": "Maximum results, 1-20. Default 5."},
            "path_prefix": {
                "type": "string",
                "description": "Optional safe relative vault path prefix, such as concepts/.",
            },
        },
        "required": ["query"],
    },
}

CONTEXT_SCHEMA = {
    "name": "homie_memory_context",
    "description": "Return compact recall context from the Homie vault. Read-only.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Context query."},
            "max_chars": {"type": "integer", "description": "Character cap, 500-12000."},
        },
        "required": ["query"],
    },
}

STATUS_SCHEMA = {
    "name": "homie_memory_status",
    "description": "Show Homie memory provider status and indexed vault counts.",
    "parameters": {"type": "object", "properties": {}, "required": []},
}


def _json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def _error(message: str) -> str:
    return _json({"success": False, "error": message})


class HomieMemoryProvider(MemoryProvider):
    """Read-only Homie Markdown vault provider for Hermes Agent."""

    def __init__(self, config: HomieMemoryConfig | None = None):
        self._config = config
        self._index: VaultIndex | None = None
        self._session_id = ""
        self._platform = ""

    @property
    def name(self) -> str:
        return "hermes-homie-memory"

    def is_available(self) -> bool:
        cfg = self._config or resolve_config()
        return cfg.available

    def get_config_schema(self) -> list[dict[str, Any]]:
        return [
            {
                "key": "vault_path",
                "description": "Absolute path to a Homie or Obsidian-compatible Markdown vault.",
                "required": True,
                "default": "",
            },
            {
                "key": "max_prefetch_chars",
                "description": "Maximum characters injected by prefetch().",
                "default": "2500",
            },
            {
                "key": "max_tool_chars",
                "description": "Maximum characters returned by context/search tools.",
                "default": "8000",
            },
        ]

    def save_config(self, values: dict[str, Any], hermes_home: str) -> None:
        save_native_config(values, hermes_home)

    def initialize(self, session_id: str, **kwargs: Any) -> None:
        self._session_id = session_id
        self._platform = str(kwargs.get("platform", ""))
        # Hermes passes the active HERMES_HOME so profile-scoped installs
        # resolve their own native config instead of a hardcoded ~/.hermes.
        hermes_home = kwargs.get("hermes_home") or None
        self._config = self._config or resolve_config(hermes_home=hermes_home)
        if not self._config.vault_path:
            logger.warning("Homie memory provider has no configured vault_path")
            return
        try:
            self._index = VaultIndex(self._config.vault_path, max_files=self._config.max_files)
        except VaultIndexError as exc:
            logger.warning("Homie memory provider unavailable: %s", exc)
            self._index = None

    def on_session_switch(
        self,
        new_session_id: str,
        *,
        parent_session_id: str = "",
        reset: bool = False,
        rewound: bool = False,
        **kwargs: Any,
    ) -> None:
        """Track session_id rotation (/resume, /branch, /reset, compression).

        The vault index is session-independent and read-only, so no other
        state needs to move.
        """
        self._session_id = new_session_id

    def system_prompt_block(self) -> str:
        if not self._index:
            return ""
        status = self._index.status()
        return (
            "# Homie Memory\n"
            "Read-only Homie vault recall is active. Use homie_memory_search, "
            "homie_memory_context, or homie_memory_status when local vault context is useful.\n"
            f"Indexed documents: {status['documents']}."
        )

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        if not self._index or not self._config:
            return ""
        query = (query or "").strip()
        if not query:
            return ""
        try:
            context = self._index.context(query, max_chars=self._config.max_prefetch_chars, limit=4)
        except VaultIndexError:
            return ""
        if not context:
            return ""
        return f"## Homie Memory Recall\n{context}"

    def sync_turn(
        self,
        user_content: str,
        assistant_content: str,
        *,
        session_id: str = "",
        messages: list[dict[str, Any]] | None = None,
    ) -> None:
        """V1 is intentionally read-only; no durable writes are performed."""

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        return [SEARCH_SCHEMA, CONTEXT_SCHEMA, STATUS_SCHEMA]

    def handle_tool_call(self, tool_name: str, args: dict[str, Any], **kwargs: Any) -> str:
        if tool_name == "homie_memory_status":
            return self._handle_status()
        if not self._index:
            return _error("Homie vault is not configured or could not be indexed.")
        try:
            if tool_name == "homie_memory_search":
                return self._handle_search(args)
            if tool_name == "homie_memory_context":
                return self._handle_context(args)
        except VaultIndexError as exc:
            return _error(str(exc))
        except Exception as exc:  # pragma: no cover - defensive fail-open contract
            logger.warning("Homie memory tool failed: %s", exc, exc_info=True)
            return _error(f"tool failed: {exc}")
        return _error(f"Unknown Homie memory tool: {tool_name}")

    def _handle_search(self, args: dict[str, Any]) -> str:
        assert self._index is not None
        limit = int(args.get("limit") or 5)
        results = self._index.search(
            str(args.get("query") or ""),
            limit=limit,
            path_prefix=args.get("path_prefix"),
        )
        return _json(
            {
                "success": True,
                "read_only": True,
                "results": [
                    {
                        "path": result.rel_path,
                        "title": result.title,
                        "score": result.score,
                        "snippet": result.snippet,
                        "headings": list(result.headings),
                    }
                    for result in results
                ],
            }
        )

    def _handle_context(self, args: dict[str, Any]) -> str:
        assert self._index is not None
        max_chars = int(args.get("max_chars") or (self._config.max_tool_chars if self._config else 8000))
        max_chars = max(500, min(max_chars, 12000))
        context = self._index.context(str(args.get("query") or ""), max_chars=max_chars)
        return _json({"success": True, "read_only": True, "context": context})

    def _handle_status(self) -> str:
        if not self._index:
            cfg = self._config or resolve_config()
            return _json(
                {
                    "success": False,
                    "available": False,
                    "read_only": True,
                    "vault_path": str(cfg.vault_path) if cfg.vault_path else "",
                    "error": "Homie vault is not configured or could not be indexed.",
                }
            )
        return _json({"success": True, "available": True, **self._index.status()})
