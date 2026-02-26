"""Botcore plugin contract and discovery."""

from __future__ import annotations

import importlib.metadata
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel

logger = logging.getLogger(__name__)


@runtime_checkable
class BotCorePlugin(Protocol):
    """Protocol that all botcore plugins must implement."""

    def register(self, registry: PluginRegistry) -> None:
        """Register commands, skills, and other extensions."""
        ...

    def config_schema(self) -> type[BaseModel] | None:
        """Return Pydantic model for [tool.botcore.plugins.<name>] validation.

        Return None if plugin needs no config.
        """
        ...


class PluginRegistry:
    """Collects registrations from plugins during startup."""

    def __init__(self) -> None:
        self._commands: list[Callable[..., Any]] = []
        self._skills_dirs: list[Path] = []
        self._cli_name: str | None = None
        self._mcp_name: str | None = None
        self._config_defaults: dict[str, Any] = {}
        self._docs: dict[str, str] = {}
        self._middleware: list[Callable[..., Any]] = []

    def add_commands(self, commands: list[Callable[..., Any]]) -> None:
        """Register command functions."""
        self._commands.extend(commands)

    def add_skills_dir(self, path: Path) -> None:
        """Register a skill directory."""
        self._skills_dirs.append(path)

    def set_cli_name(self, name: str) -> None:
        """Set CLI branding name."""
        self._cli_name = name

    def set_mcp_name(self, name: str) -> None:
        """Set MCP server identity."""
        self._mcp_name = name

    def add_docs(self, topic: str, content: str) -> None:
        """Register documentation for a topic (shown via {name}-docs tool)."""
        self._docs[topic] = content

    def add_middleware(self, middleware: Callable[..., Any]) -> None:
        """Register a middleware callable for command pre/post-processing."""
        self._middleware.append(middleware)

    def config_defaults(self) -> dict[str, Any]:
        """Return plugin config defaults."""
        return dict(self._config_defaults)

    @property
    def commands(self) -> list[Callable[..., Any]]:
        return list(self._commands)

    @property
    def skills_dirs(self) -> list[Path]:
        return list(self._skills_dirs)

    @property
    def cli_name(self) -> str | None:
        return self._cli_name

    @property
    def mcp_name(self) -> str | None:
        return self._mcp_name

    @property
    def docs(self) -> dict[str, str]:
        return dict(self._docs)

    @property
    def middleware(self) -> list[Callable[..., Any]]:
        return list(self._middleware)


def discover_plugins() -> dict[str, BotCorePlugin]:
    """Discover installed plugins via the botcore.plugins entry point group.

    Returns:
        Dict mapping plugin name to loaded plugin instance.
    """
    plugins: dict[str, BotCorePlugin] = {}

    eps = importlib.metadata.entry_points()
    if hasattr(eps, "select"):
        botcore_eps = eps.select(group="botcore.plugins")
    else:
        botcore_eps = eps.get("botcore.plugins", [])

    for ep in botcore_eps:
        try:
            plugin_cls = ep.load()
            # Support both class-based (instantiate) and instance-based plugins
            plugin = plugin_cls() if isinstance(plugin_cls, type) else plugin_cls
            plugins[ep.name] = plugin
        except Exception:
            logger.warning("Failed to load plugin entry point '%s'", ep.name, exc_info=True)

    return plugins
