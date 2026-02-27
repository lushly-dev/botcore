# Orchestrator State Serialization

## Problem

The agent orchestrator's state (agents, tasks, configuration) is stored only in memory and lost on session end. This blocks server-mode persistence, CI/CD checkpoint recovery, dashboard visualization, and distributed orchestration.

## Solution

Add a pluggable backend system for persisting orchestrator state as point-in-time snapshots, with a JSON file implementation included.

## Architecture

### Snapshot Model

A single `OrchestratorSnapshot` Pydantic model wraps the real domain models directly — no parallel snapshot models that could drift out of sync:

```python
class OrchestratorSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = "1.0"
    timestamp: datetime  # auto-populated, UTC
    config: AgentsPluginConfig
    agents: dict[str, AgentState]
    tasks: dict[str, Task]
```

### Backend Protocol

```python
@runtime_checkable
class OrchestratorStateBackend(Protocol):
    async def save(self, snapshot: OrchestratorSnapshot) -> None: ...
    async def load(self) -> OrchestratorSnapshot | None: ...
```

Construction is backend-specific (file path, DB URL, etc.).

### JSON File Backend

```python
class JsonStateBackend:
    def __init__(self, path: Path, retention_hours: int = 168) -> None: ...
    async def save(self, snapshot: OrchestratorSnapshot) -> None: ...
    async def load(self) -> OrchestratorSnapshot | None: ...
```

- Uses `asyncio.to_thread()` for all file I/O (non-blocking)
- Atomic writes via `tempfile.mkstemp` + `os.replace`
- Temp files cleaned up on failure
- Stale snapshots (older than `retention_hours`) ignored on load

### Orchestrator API

```python
class AgentOrchestrator:
    def __init__(self, config, *, backend: OrchestratorStateBackend | None = None): ...
    async def save_state(self) -> CommandResult[dict]: ...
    async def load_state(self) -> CommandResult[dict]: ...
```

**`save_state()`** builds a deep-copy snapshot (clearing `session_id` since sessions are not portable) and delegates to the backend. Returns `success(data={"saved": True, "agents": N, "tasks": N, "timestamp": ...})`.

**`load_state()`** reads from the backend and restores state. All restored agents are forced to `status="stopped"` with cleared session metadata. Returns `success(data={"restored": True, ...})` or `{"restored": False}` if no snapshot exists.

Error codes: `NO_BACKEND`, `STATE_SAVE_ERROR`, `STATE_LOAD_ERROR`.

### Commands

Two thin MCP wrappers registered alongside existing commands:

| Command | Description |
|---------|-------------|
| `state_save` | Persist orchestrator state to configured backend |
| `state_load` | Restore orchestrator state from configured backend |

## Restore Semantics

- Agents restored with `status="stopped"`, `session_id=""`, `active_tasks=[]`, `started_at=None`
- Tasks restored as-is (full `Task` model)
- Configuration replaced from snapshot

## Future Work

- Auto-save on state changes (on task complete, agent stop, etc.)
- Additional backends (SQLite, Redis)
- Incremental/diff-based snapshots
