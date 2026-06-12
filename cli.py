"""CLI helpers for the active hermes-homie-memory provider."""

from __future__ import annotations

import json
from pathlib import Path

try:
    from .config import resolve_config
    from .vault_index import VaultIndex, VaultIndexError
except ImportError:  # pragma: no cover - direct import fallback for local tests
    from config import resolve_config
    from vault_index import VaultIndex, VaultIndexError


def _print_json(data: dict) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def hermes_homie_memory_command(args) -> None:
    cfg = resolve_config()
    sub = getattr(args, "homie_command", "status")

    if sub == "config":
        _print_json(
            {
                "vault_path": str(cfg.vault_path) if cfg.vault_path else "",
                "max_prefetch_chars": cfg.max_prefetch_chars,
                "max_tool_chars": cfg.max_tool_chars,
                "max_files": cfg.max_files,
                "available": cfg.available,
            }
        )
        return

    if not cfg.vault_path:
        _print_json({"success": False, "error": "vault_path is not configured"})
        return

    try:
        index = VaultIndex(Path(cfg.vault_path), max_files=cfg.max_files)
        if sub == "search":
            results = index.search(getattr(args, "query", ""), limit=getattr(args, "limit", 5))
            _print_json(
                {
                    "success": True,
                    "results": [
                        {"path": item.rel_path, "title": item.title, "score": item.score, "snippet": item.snippet}
                        for item in results
                    ],
                }
            )
            return
        _print_json({"success": True, **index.status()})
    except VaultIndexError as exc:
        _print_json({"success": False, "error": str(exc)})


def register_cli(subparser) -> None:
    subs = subparser.add_subparsers(dest="homie_command")

    subs.add_parser("status", help="Show Homie memory provider status")
    subs.add_parser("config", help="Show resolved Homie memory provider config")
    search = subs.add_parser("search", help="Search the configured Homie vault")
    search.add_argument("query", help="Search query")
    search.add_argument("--limit", type=int, default=5, help="Maximum results")

    subparser.set_defaults(func=hermes_homie_memory_command)
