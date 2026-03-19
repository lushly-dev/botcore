"""Botcore — shared bot infrastructure for config, plugins, and commands."""

from botcore.config import (
    BotCoreConfig,
    EnvConfig,
    PackageOverrideConfig,
    SkillsConfig,
    get_config_for_path,
    load_config,
)
from botcore.plugin import (
    BotCorePlugin,
    PluginRegistry,
    discover_plugins,
)
from botcore.registry import (
    get_client,
    registry,
    reset_client,
)
from botcore.server import build_docs, build_namespace, create_mcp_server

__version__ = "0.3.3"

__all__ = [
    "__version__",
    # Config
    "BotCoreConfig",
    "SkillsConfig",
    "PackageOverrideConfig",
    "EnvConfig",
    "load_config",
    "get_config_for_path",
    # Plugin
    "PluginRegistry",
    "BotCorePlugin",
    "discover_plugins",
    # Registry
    "registry",
    "get_client",
    "reset_client",
    # Server
    "build_namespace",
    "build_docs",
    "create_mcp_server",
]
