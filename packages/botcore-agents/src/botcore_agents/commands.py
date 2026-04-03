"""Agent orchestration commands.

Each command follows the botcore convention: ``async def`` returning
``CommandResult[T]`` and using ``success()`` / ``error()`` from AFD.
"""

from __future__ import annotations

import logging
from pathlib import Path

from afd import CommandResult

from .config import AgentsPluginConfig, get_agents_config
from .orchestrator import get_orchestrator, reset_orchestrator
from .state import JsonStateBackend, OrchestratorStateBackend

logger = logging.getLogger(__name__)

# Module-level config — set by the plugin at startup, or lazy-default.
_config: AgentsPluginConfig | None = None
_backend: OrchestratorStateBackend | None = None


def _get_config() -> AgentsPluginConfig:
    global _config
    if _config is None:
        _config = get_agents_config()
    return _config


def set_config(config: AgentsPluginConfig | None) -> None:
    """Allow the plugin to inject config at registration time."""
    global _backend, _config
    _config = config
    _backend = None
    reset_orchestrator()


def _get_backend() -> OrchestratorStateBackend | None:
    global _backend
    if _backend is not None:
        return _backend

    config = _get_config()
    if not config.state.enabled:
        return None

    from botcore.utils.workspace import find_workspace

    workspace = find_workspace()
    path = config.state.resolve_path(workspace)
    _backend = JsonStateBackend(path, retention_hours=config.state.retention_hours)
    return _backend


def _get_orch():
    return get_orchestrator(_get_config(), backend=_get_backend())


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


async def agent_create(name: str) -> CommandResult[dict]:
    """Create an agent from the configured agent pool."""
    return await _get_orch().create_agent(name)


async def agent_delete(name: str) -> CommandResult[dict]:
    """Delete a stopped agent from the configured pool."""
    return await _get_orch().delete_agent(name)


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
    agent: str = "",
    role: str = "",
    priority: int = 5,
) -> CommandResult[dict]:
    """Assign a task to a running agent or a role.

    Pass *agent* to target a specific instance, or *role* to let the
    orchestrator pick an idle agent of that role (spawning a new instance
    if all are busy and pool capacity allows).
    """
    return await _get_orch().assign_task(description, agent=agent, role=role, priority=priority)


async def task_resume(
    task_id: str,
    agent: str = "",
    role: str = "",
) -> CommandResult[dict]:
    """Resume a pending or assigned task."""
    return await _get_orch().resume_task(task_id=task_id, agent=agent, role=role)


async def task_status(task_id: str) -> CommandResult[dict]:
    """Get task details by task ID."""
    return _get_orch().get_task(task_id)


async def state_save() -> CommandResult[dict]:
    """Persist orchestrator state to the configured backend."""
    return await _get_orch().save_state()


async def state_load() -> CommandResult[dict]:
    """Restore orchestrator state from the configured backend."""
    return await _get_orch().load_state()


AGENT_COMMANDS: list = [
    agent_create,
    agent_delete,
    agent_start,
    agent_stop,
    agent_status,
    agent_heartbeat,
    task_assign,
    task_resume,
    task_status,
    state_save,
    state_load,
]
