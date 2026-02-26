"""Connectors plugin — wires into botcore's plugin system."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from botcore.plugin import PluginRegistry
from pydantic import BaseModel

from botcore_connectors.config import ConnectorsConfig

_CONNECTORS_DOCS = """\
# Connectors Plugin

Typed HTTP connectors for external services: GitHub, Azure Blob, Azure Queue, Email.

## Configuration

```toml
[tool.botcore.plugins.connectors]
enabled = ["github"]

[tool.botcore.plugins.connectors.github]
default_repo = "org/repo"
api_version = "2022-11-28"

[tool.botcore.plugins.connectors.auth]
github_token_env = "GH_TOKEN"
```

## Supported Connectors

- **github** — GitHub REST API v3
- **azure_blob** — Azure Blob Storage
- **azure_queue** — Azure Queue (Service Bus)
- **email** — Email via Microsoft Graph
"""


class ConnectorsPlugin:
    """Connectors plugin for botcore.

    Supports two-phase initialisation:
    1. ``discover_plugins()`` instantiates with no args → ``register()`` sets
       MCP name + docs but zero commands (safe for entry-point discovery).
    2. ``configure()`` injects validated config later → enables command
       filtering based on ``enabled`` list.
    """

    def __init__(self, config: ConnectorsConfig | None = None) -> None:
        self._config = config
        self._registered_prefixes: list[str] = []

    def configure(self, config: ConnectorsConfig) -> None:
        """Inject config after construction (two-phase init)."""
        self._config = config

    @property
    def config(self) -> ConnectorsConfig | None:
        return self._config

    @property
    def enabled_prefixes(self) -> list[str]:
        """Return enabled connector names for agent-scoping."""
        if self._config is None:
            return []
        return list(self._config.enabled)

    def register(self, registry: PluginRegistry) -> None:
        """Register plugin identity, docs, and commands.

        Always sets MCP name and docs.  Commands are only registered for
        connectors listed in ``enabled`` (Phase 1 returns none regardless).
        """
        registry.set_mcp_name("connectors")
        registry.add_docs("connectors", _CONNECTORS_DOCS)

        if self._config is not None:
            for name in self._config.enabled:
                commands = self._get_commands_for(name)
                if commands:
                    registry.add_commands(commands)
                self._registered_prefixes.append(name)

    def config_schema(self) -> type[BaseModel]:
        """Return Pydantic model for config validation."""
        return ConnectorsConfig

    def _get_commands_for(self, name: str) -> list[Callable[..., Any]]:
        """Return commands for a named connector.

        Phase 1: returns [] for all connectors.  Spec 05 will populate
        actual command functions per connector type.
        """
        return []
