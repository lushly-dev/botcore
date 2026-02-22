"""Botcore command registry using AFD DirectClient."""

from __future__ import annotations

from afd import (
    DirectClient,
    SimpleRegistry,
    create_direct_client,
)

# Global registry instance
registry = SimpleRegistry()

# Global client (lazy initialized)
_client: DirectClient | None = None


def get_client(
    source: str | None = None,
    debug: bool = False,
) -> DirectClient:
    """Get the global DirectClient for inter-module calls.

    The client is lazily initialized and reused across calls.

    Args:
        source: Optional source identifier for tracing.
        debug: Enable debug logging.

    Returns:
        DirectClient instance.
    """
    global _client
    if _client is None:
        _client = create_direct_client(
            registry,
            source=source or "botcore",
            debug=debug,
        )
    return _client


def reset_client() -> None:
    """Reset the global client (primarily for testing)."""
    global _client
    _client = None


__all__ = [
    "registry",
    "get_client",
    "reset_client",
]
