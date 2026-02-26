"""Agent orchestration commands.

Each command follows the botcore convention: ``async def`` returning
``CommandResult[T]`` and using ``success()`` / ``error()`` from AFD.
"""

from __future__ import annotations

import logging

from afd import CommandResult

from .config import AgentsPluginConfig, get_agents_config
from .orchestrator import get_orchestrator

logger = logging.getLogger(__name__)

# Module-level config — set by the plugin at startup, or lazy-default.
_config: AgentsPluginConfig | None = None


def _get_config() -> AgentsPluginConfig:
    global _config
    if _config is None:
        _config = get_agents_config()
    return _config


def set_config(config: AgentsPluginConfig) -> None:
    """Allow the plugin to inject config at registration time."""
    global _config
    _config = config


def _get_orch():
    return get_orchestrator(_get_config())


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


async def agent_create(name: str) -> CommandResult[dict]:
    """Create an agent from the configured agent pool."""
    return await _get_orch().create_agent(name)


async def agent_start(name: str) -> CommandResult[dict]:
    """Start a created agent by initialising its LLM session."""
    return await _get_orch().start_agent(name)


async def agent_stop(name: str) -> CommandResult[dict]:
    """Stop a running agent and destroy its LLM session."""
    return await _get_orch().stop_agent(name)


async def agent_status(name: str) -> CommandResult[dict]:
    """Get the health snapshot for a named agent."""
    return _get_orch().get_agent_status(name)


async def agent_heartbeat(name: str) -> CommandResult[dict]:
    """Update agent heartbeat and return health status."""
    return _get_orch().heartbeat(name)


async def task_assign(
    description: str,
    agent: str,
    priority: int = 5,
) -> CommandResult[dict]:
    """Assign a task to a running agent for synchronous execution."""
    return await _get_orch().assign_task(description, agent, priority)


async def task_status(task_id: str) -> CommandResult[dict]:
    """Get task details by task ID."""
    return _get_orch().get_task(task_id)


AGENT_COMMANDS: list = [
    agent_create,
    agent_start,
    agent_stop,
    agent_status,
    agent_heartbeat,
    task_assign,
    task_status,
]
