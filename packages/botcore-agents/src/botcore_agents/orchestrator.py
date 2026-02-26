"""Agent orchestrator — pool management, task assignment, session lifecycle."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from afd import CommandResult, error, success
from botcore_llm.commands import llm_chat, llm_session_create, llm_session_destroy

from .config import AgentsPluginConfig
from .models import AgentHealth, AgentState, Task

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Manages agent lifecycle and task execution.

    Phase 1: synchronous task execution (no background loop).
    """

    def __init__(self, config: AgentsPluginConfig) -> None:
        self._config = config
        self._agents: dict[str, AgentState] = {}
        self._tasks: dict[str, Task] = {}

    @property
    def config(self) -> AgentsPluginConfig:
        return self._config

    @property
    def agents(self) -> dict[str, AgentState]:
        return dict(self._agents)

    @property
    def tasks(self) -> dict[str, Task]:
        return dict(self._tasks)

    async def create_agent(self, name: str) -> CommandResult[dict]:
        """Create an agent from config. Does not start it."""
        if name not in self._config.agents:
            return error(
                "AGENT_NOT_CONFIGURED",
                f"No agent configuration for {name!r}",
                suggestion="Add agent config under [plugins.agents.agents] in botcore.toml",
            )

        if name in self._agents:
            return error(
                "AGENT_ALREADY_EXISTS",
                f"Agent {name!r} already exists",
                suggestion="Use agent_start to start it, or agent_stop then recreate",
            )

        if len(self._agents) >= self._config.max_agents:
            return error(
                "MAX_AGENTS_REACHED",
                f"Agent pool is full ({self._config.max_agents} max)",
                suggestion="Stop or remove an existing agent first",
            )

        agent_config = self._config.agents[name]
        health = AgentHealth(name=name, status="stopped")
        state = AgentState(config=agent_config, health=health)
        self._agents[name] = state

        return success(
            data={"name": name, "status": "stopped"},
            reasoning=f"Agent {name!r} created with status=stopped",
        )

    async def start_agent(self, name: str) -> CommandResult[dict]:
        """Start an agent by creating an LLM session."""
        if name not in self._agents:
            return error("AGENT_NOT_FOUND", f"Agent {name!r} does not exist")

        state = self._agents[name]
        if state.health.status != "stopped":
            return error(
                "AGENT_ALREADY_STARTED",
                f"Agent {name!r} is already {state.health.status}",
            )

        model = state.config.model or self._config.default_model
        tools = state.config.skills or None
        system_prompt = state.config.system_prompt or None

        result = await llm_session_create(
            model=model,
            tools=tools,
            system_prompt=system_prompt,
        )

        if not result.success:
            return error(
                "SESSION_CREATE_ERROR",
                f"Failed to create LLM session for {name!r}: {result.error.message}",
            )

        now = datetime.now(UTC)
        state.session_id = result.data["session_id"]
        state.started_at = now
        state.health.status = "idle"
        state.health.last_heartbeat = now

        return success(
            data={
                "name": name,
                "status": "idle",
                "session_id": state.session_id,
            },
            reasoning=f"Agent {name!r} started with session {state.session_id}",
        )

    async def stop_agent(self, name: str) -> CommandResult[dict]:
        """Stop an agent and destroy its LLM session."""
        if name not in self._agents:
            return error("AGENT_NOT_FOUND", f"Agent {name!r} does not exist")

        state = self._agents[name]
        if state.health.status == "stopped":
            return error(
                "AGENT_NOT_STARTED",
                f"Agent {name!r} is not started",
            )

        # Cancel active tasks
        cancelled_tasks = []
        for task_id in list(state.active_tasks):
            if task_id in self._tasks:
                task = self._tasks[task_id]
                task.status = "cancelled"
                task.completed_at = datetime.now(UTC)
                cancelled_tasks.append(task_id)
        state.active_tasks.clear()

        # Destroy session
        if state.session_id:
            await llm_session_destroy(state.session_id)
            state.session_id = ""

        state.health.status = "stopped"
        state.health.current_task = ""
        state.started_at = None

        return success(
            data={
                "name": name,
                "status": "stopped",
                "cancelled_tasks": cancelled_tasks,
            },
            reasoning=f"Agent {name!r} stopped, {len(cancelled_tasks)} task(s) cancelled",
        )

    async def assign_task(
        self,
        description: str,
        agent: str,
        priority: int = 5,
    ) -> CommandResult[dict]:
        """Assign and execute a task synchronously via the agent's LLM session."""
        if agent not in self._agents:
            return error("AGENT_NOT_FOUND", f"Agent {agent!r} does not exist")

        state = self._agents[agent]
        if state.health.status == "stopped":
            return error(
                "AGENT_NOT_STARTED",
                f"Agent {agent!r} is not started",
            )

        if len(state.active_tasks) >= state.config.max_concurrent_tasks:
            return error(
                "AGENT_AT_CAPACITY",
                f"Agent {agent!r} is at capacity "
                f"({state.config.max_concurrent_tasks} concurrent tasks)",
            )

        # Create task
        task = Task(
            description=description,
            assigned_agent=agent,
            status="running",
            priority=priority,
            started_at=datetime.now(UTC),
        )
        self._tasks[task.id] = task
        state.active_tasks.append(task.id)
        state.health.status = "busy"
        state.health.current_task = task.id

        # Execute via LLM
        try:
            chat_result = await llm_chat(
                session_id=state.session_id,
                message=description,
            )

            if chat_result.success:
                task.status = "completed"
                task.result = chat_result.data.get("content", "")
                state.health.tasks_completed += 1
            else:
                task.status = "failed"
                task.result = chat_result.error.message
                state.health.tasks_failed += 1
        except Exception as exc:
            task.status = "failed"
            task.result = str(exc)
            state.health.tasks_failed += 1
            logger.warning("Task %s execution error: %s", task.id, exc)

        task.completed_at = datetime.now(UTC)

        # Clean up active task tracking
        if task.id in state.active_tasks:
            state.active_tasks.remove(task.id)
        state.health.current_task = ""
        state.health.status = "idle" if not state.active_tasks else "busy"

        if task.status == "failed":
            return error(
                "TASK_EXECUTION_ERROR",
                f"Task failed: {task.result}",
            )

        return success(
            data={
                "task_id": task.id,
                "status": task.status,
                "result": task.result,
                "agent": agent,
            },
            reasoning=f"Task {task.id} completed by agent {agent!r}",
        )

    def get_agent_status(self, name: str) -> CommandResult[dict]:
        """Return health snapshot for an agent."""
        if name not in self._agents:
            return error("AGENT_NOT_FOUND", f"Agent {name!r} does not exist")

        state = self._agents[name]
        now = datetime.now(UTC)
        uptime = 0.0
        if state.started_at:
            uptime = (now - state.started_at).total_seconds()

        health = state.health.model_copy(update={"uptime_seconds": uptime})
        return success(
            data=health.model_dump(mode="json"),
            reasoning=f"Agent {name!r} status: {health.status}",
        )

    def get_task(self, task_id: str) -> CommandResult[dict]:
        """Return task details."""
        if task_id not in self._tasks:
            return error("TASK_NOT_FOUND", f"No task with id {task_id!r}")

        task = self._tasks[task_id]
        return success(
            data=task.model_dump(mode="json"),
            reasoning=f"Task {task_id} status: {task.status}",
        )

    def heartbeat(self, name: str) -> CommandResult[dict]:
        """Update agent heartbeat and return health."""
        if name not in self._agents:
            return error("AGENT_NOT_FOUND", f"Agent {name!r} does not exist")

        state = self._agents[name]
        if state.health.status == "stopped":
            return error(
                "AGENT_NOT_STARTED",
                f"Agent {name!r} is not started",
            )

        now = datetime.now(UTC)
        state.health.last_heartbeat = now

        uptime = 0.0
        if state.started_at:
            uptime = (now - state.started_at).total_seconds()

        health = state.health.model_copy(update={"uptime_seconds": uptime})
        return success(
            data=health.model_dump(mode="json"),
            reasoning=f"Heartbeat for {name!r} at {now.isoformat()}",
        )


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_orchestrator: AgentOrchestrator | None = None


def get_orchestrator(config: AgentsPluginConfig | None = None) -> AgentOrchestrator:
    """Return the module-level orchestrator singleton.

    If *config* is provided and no orchestrator exists, one is created.
    If called without config and none exists, creates one with defaults.
    """
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator(config or AgentsPluginConfig())
    return _orchestrator


def reset_orchestrator() -> None:
    """Reset the singleton (useful in tests)."""
    global _orchestrator
    _orchestrator = None
