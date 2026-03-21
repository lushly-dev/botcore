"""Agent orchestrator — pool management, task assignment, session lifecycle."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from afd import CommandResult, error, success
from botcore_llm.commands import llm_chat, llm_session_create, llm_session_destroy

from .config import AgentConfig, AgentsPluginConfig
from .models import AgentHealth, AgentState, Task

if TYPE_CHECKING:
    from .state import OrchestratorSnapshot, OrchestratorStateBackend

logger = logging.getLogger(__name__)

# Cached command namespace — avoids re-discovering plugins on every start.
_namespace: dict[str, Callable[..., Any]] | None = None


def resolve_connector_commands(
    connectors: list[str],
    connector_commands: list[str],
    namespace: dict[str, Any],
) -> list[str]:
    """Resolve which connector commands an agent may access.

    Resolution order:
    1. *connector_commands* non-empty → return those directly (explicit override).
    2. *connectors* empty → ``[]`` (deny-by-default).
    3. ``"*"`` in *connectors* → all known connector-prefixed commands.
    4. Otherwise → prefix-filter *namespace* keys against *connectors*.
    """
    # 1. Explicit command list takes precedence
    if connector_commands:
        missing = [c for c in connector_commands if c not in namespace]
        if missing:
            logger.warning("connector_commands not in namespace: %s", missing)
        return list(connector_commands)

    # 2. Deny-by-default
    if not connectors:
        return []

    # 3. Wildcard — all connector-prefixed commands
    if "*" in connectors:
        try:
            from botcore_connectors.config import KNOWN_CONNECTORS
        except ImportError:
            KNOWN_CONNECTORS: frozenset[str] = frozenset()
        prefixes = tuple(f"{c}_" for c in KNOWN_CONNECTORS)
        return [k for k in namespace if any(k.startswith(p) for p in prefixes)]

    # 4. Prefix-filter against connectors list
    prefixes = tuple(f"{c}_" for c in connectors)
    return [k for k in namespace if any(k.startswith(p) for p in prefixes)]


class AgentOrchestrator:
    """Manages agent lifecycle and task execution.

    Phase 1: synchronous task execution (no background loop).
    """

    def __init__(
        self,
        config: AgentsPluginConfig,
        *,
        backend: OrchestratorStateBackend | None = None,
    ) -> None:
        self._config = config
        self._agents: dict[str, AgentState] = {}
        self._tasks: dict[str, Task] = {}
        self._backend = backend

    @property
    def config(self) -> AgentsPluginConfig:
        return self._config

    @property
    def agents(self) -> dict[str, AgentState]:
        return dict(self._agents)

    @property
    def tasks(self) -> dict[str, Task]:
        return dict(self._tasks)

    def _resolve_tools(self, config: AgentConfig) -> list[str]:
        """Build the combined tools list from skills + connector commands."""
        tools = list(config.skills)

        if config.connectors or config.connector_commands:
            global _namespace
            if _namespace is None:
                from botcore.server import build_namespace

                _namespace, _ = build_namespace()

            tools.extend(resolve_connector_commands(
                config.connectors,
                config.connector_commands,
                _namespace,
            ))

        return tools or []

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
            undo_command="agent_delete",
            undo_args={"name": name},
        )

    async def delete_agent(self, name: str) -> CommandResult[dict]:
        """Delete a stopped agent from the pool."""
        if name not in self._agents:
            return error("AGENT_NOT_FOUND", f"Agent {name!r} does not exist")

        state = self._agents[name]
        if state.health.status != "stopped":
            return error(
                "AGENT_MUST_BE_STOPPED",
                f"Agent {name!r} must be stopped before deletion",
                suggestion="Use agent_stop before agent_delete",
            )

        del self._agents[name]

        return success(
            data={"name": name, "deleted": True},
            reasoning=f"Agent {name!r} deleted from the pool",
            undo_command="agent_create",
            undo_args={"name": name},
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
        tools = self._resolve_tools(state.config)
        system_prompt = state.config.system_prompt or None

        result = await llm_session_create(
            model=model,
            tools=tools,
            system_prompt=system_prompt,
            permissions=state.config.permissions,
            agent_name=name,
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

    async def _resolve_agent_for_role(self, role: str) -> CommandResult[dict]:
        """Find an idle agent for *role*, or spawn a new instance.

        Search order:
        1. Existing idle agent with matching role → use it
        2. Pool has capacity → create + start a new instance from the role template
        3. All at capacity → return error
        """
        # 1. Find an instance with capacity
        for name, state in self._agents.items():
            if (
                state.config.role == role
                and state.health.status in ("idle", "busy")
                and len(state.active_tasks) < state.config.max_concurrent_tasks
            ):
                return success(
                    data={"name": name},
                    reasoning=f"Reusing agent {name!r} for role {role!r}",
                )

        # 2. Find the config template for this role
        template_config = self._find_role_config(role)
        if template_config is None:
            return error(
                "ROLE_NOT_CONFIGURED",
                f"No agent configuration with role={role!r}",
                suggestion=f'Add role = "{role}" to an agent config in botcore.toml',
            )

        # 3. Check pool capacity
        if len(self._agents) >= self._config.max_agents:
            return error(
                "MAX_AGENTS_REACHED",
                f"Agent pool is full ({self._config.max_agents} max) "
                f"and no idle {role!r} agents available",
                suggestion="Stop idle agents or increase max_agents",
            )

        # 4. Create + start a new instance
        instance_name = self._next_instance_name(role)
        agent_config = template_config.model_copy(update={"name": instance_name})
        health = AgentHealth(name=instance_name, status="stopped")
        state = AgentState(config=agent_config, health=health)
        self._agents[instance_name] = state

        start_result = await self.start_agent(instance_name)
        if not start_result.success:
            # Clean up the created-but-failed-to-start agent
            del self._agents[instance_name]
            return error(
                "ROLE_SPAWN_FAILED",
                f"Spawned {instance_name!r} for role {role!r} but failed to start: "
                f"{start_result.error.message}",
            )

        return success(
            data={"name": instance_name, "spawned": True},
            reasoning=f"Spawned new agent {instance_name!r} for role {role!r}",
        )

    def _find_role_config(self, role: str) -> AgentConfig | None:
        """Return the first configured agent template matching *role*.

        Uses insertion-order (dict order) so the first matching entry
        in ``[plugins.agents.agents]`` wins.
        """
        for cfg in self._config.agents.values():
            if cfg.role == role:
                return cfg
        return None

    def _next_instance_name(self, role: str) -> str:
        """Generate the next sequential instance name for *role*."""
        idx = 1
        while f"{role}-{idx}" in self._agents:
            idx += 1
        return f"{role}-{idx}"

    async def assign_task(
        self,
        description: str,
        agent: str = "",
        role: str = "",
        priority: int = 5,
    ) -> CommandResult[dict]:
        """Assign and execute a task synchronously via an agent's LLM session.

        Supply *agent* to target a specific instance, or *role* to let the
        orchestrator pick an idle instance (or spawn a new one from the role's
        config template).
        """
        if not agent and not role:
            return error(
                "NO_TARGET",
                "Provide either 'agent' or 'role' to assign the task",
                suggestion="Pass agent='name' or role='pm'",
            )

        # Role-based routing: find an idle agent or spawn a new instance
        if role and not agent:
            resolved = await self._resolve_agent_for_role(role)
            if not resolved.success:
                return resolved
            agent = resolved.data["name"]

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

    # -- State serialization ------------------------------------------------

    def _build_snapshot(self) -> OrchestratorSnapshot:
        """Create a snapshot of the current orchestrator state.

        Deep-copies agents and tasks.  Session IDs are cleared in the copy
        because sessions are not portable across processes.
        """
        from .state import OrchestratorSnapshot

        agents: dict[str, AgentState] = {}
        for name, state in self._agents.items():
            copied = state.model_copy(deep=True)
            copied.session_id = ""
            agents[name] = copied

        tasks = {tid: task.model_copy(deep=True) for tid, task in self._tasks.items()}

        return OrchestratorSnapshot(
            config=self._config.model_copy(deep=True),
            agents=agents,
            tasks=tasks,
        )

    def _restore_from_snapshot(self, snapshot: OrchestratorSnapshot) -> None:
        """Replace live state with *snapshot* contents.

        Deep-copies snapshot data so the original is not mutated.
        Restored agents are forced to ``stopped`` with cleared session
        metadata since sessions are not portable.
        """
        logger.info("Replacing orchestrator config from snapshot (version=%s)", snapshot.version)
        self._config = snapshot.config.model_copy(deep=True)
        self._tasks = {tid: t.model_copy(deep=True) for tid, t in snapshot.tasks.items()}

        agents: dict[str, AgentState] = {}
        for name, state in snapshot.agents.items():
            copied = state.model_copy(deep=True)
            copied.health.status = "stopped"
            copied.health.current_task = ""
            copied.session_id = ""
            copied.active_tasks = []
            copied.started_at = None
            agents[name] = copied

        self._agents = agents

    async def save_state(self) -> CommandResult[dict]:
        """Persist current state via the configured backend."""
        if self._backend is None:
            return error(
                "NO_BACKEND",
                "No state backend configured",
                suggestion="Pass a backend= when constructing the orchestrator",
            )
        try:
            snapshot = self._build_snapshot()
            await self._backend.save(snapshot)
            return success(
                data={
                    "saved": True,
                    "agents": len(snapshot.agents),
                    "tasks": len(snapshot.tasks),
                    "timestamp": snapshot.timestamp.isoformat(),
                },
                reasoning="Orchestrator state saved",
            )
        except Exception as exc:
            logger.warning("State save failed: %s", exc)
            return error("STATE_SAVE_ERROR", f"Failed to save state: {exc}")

    async def load_state(self) -> CommandResult[dict]:
        """Restore state from the configured backend."""
        if self._backend is None:
            return error(
                "NO_BACKEND",
                "No state backend configured",
                suggestion="Pass a backend= when constructing the orchestrator",
            )
        try:
            snapshot = await self._backend.load()
            if snapshot is None:
                return success(
                    data={"restored": False},
                    reasoning="No saved state found (missing or stale)",
                )
            self._restore_from_snapshot(snapshot)
            return success(
                data={
                    "restored": True,
                    "agents": len(self._agents),
                    "tasks": len(self._tasks),
                    "timestamp": snapshot.timestamp.isoformat(),
                },
                reasoning="Orchestrator state restored from snapshot",
            )
        except Exception as exc:
            logger.warning("State load failed: %s", exc)
            return error("STATE_LOAD_ERROR", f"Failed to load state: {exc}")

    # TODO: auto-save on state changes is deferred to a future iteration.


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_orchestrator: AgentOrchestrator | None = None


def get_orchestrator(
    config: AgentsPluginConfig | None = None,
    *,
    backend: OrchestratorStateBackend | None = None,
) -> AgentOrchestrator:
    """Return the module-level orchestrator singleton.

    If *config* is provided and no orchestrator exists, one is created.
    If called without config and none exists, creates one with defaults.
    """
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator(config or AgentsPluginConfig(), backend=backend)
    elif backend is not None:
        logger.warning(
            "get_orchestrator() called with backend= but singleton already exists; "
            "updating backend on existing instance"
        )
        _orchestrator._backend = backend
    return _orchestrator


def reset_orchestrator() -> None:
    """Reset the singleton (useful in tests)."""
    global _orchestrator
    _orchestrator = None
