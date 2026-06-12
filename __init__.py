"""Hermes memory-provider entrypoint for read-only Homie vault recall."""

from __future__ import annotations

try:
    from .provider import HomieMemoryProvider
except ImportError:  # pragma: no cover - direct import fallback for local tests
    from provider import HomieMemoryProvider


def register(ctx) -> None:
    """Register the provider with Hermes' memory-provider collector."""
    ctx.register_memory_provider(HomieMemoryProvider())


__all__ = ["HomieMemoryProvider", "register"]
