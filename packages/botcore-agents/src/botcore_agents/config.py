"""Agent orchestration configuration models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AgentConfig(BaseModel):
    """Configuration for a single agent."""

    model_config = ConfigDict(extra="forbid")

    name: str = ""
    model: str = ""
    skills: list[str] = Field(default_factory=list)
    connectors: list[str] = Field(default_factory=list)
    memory_scope: Literal["session", "agent", "global"] = "session"
    max_concurrent_tasks: int = Field(default=1, ge=1, le=10)
    heartbeat_interval: int = Field(default=30, ge=5, le=300)
    system_prompt: str = ""
    is_lead: bool = False


class AgentsPluginConfig(BaseModel):
    """Top-level agents plugin configuration.

    Mapped from ``[tool.botcore.plugins.agents]`` in botcore.toml.
    """

    model_config = ConfigDict(extra="forbid")

    agents: dict[str, AgentConfig] = Field(default_factory=dict)
    default_model: str = "gpt-4.1"
    max_agents: int = Field(default=10, ge=1, le=50)


def get_agents_config(plugin_config: dict[str, Any] | None = None) -> AgentsPluginConfig:
    """Extract ``AgentsPluginConfig`` from a plugin config dict.

    Args:
        plugin_config: Raw dict from botcore plugin config section, or None.

    Returns:
        Validated AgentsPluginConfig instance.
    """
    if plugin_config is None:
        return AgentsPluginConfig()
    return AgentsPluginConfig.model_validate(plugin_config)
