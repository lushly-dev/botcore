"""Documentation strings for the agents plugin."""

AGENTS_DOCS = """\
# Agent Orchestration Commands (Phase 1)

Single-agent lifecycle management with LLM-backed task execution.

| Command | Description |
|---------|-------------|
| `agent_create` | Create an agent from config (does not start it) |
| `agent_start` | Start an agent — creates an LLM session |
| `agent_stop` | Stop an agent — destroys session, cancels tasks |
| `agent_status` | Get agent health snapshot |
| `agent_heartbeat` | Update heartbeat timestamp, return health |
| `task_assign` | Assign a task to a running agent (sync execution) |
| `task_status` | Get task details by ID |
| `state_save` | Persist orchestrator state to configured backend |
| `state_load` | Restore orchestrator state from configured backend |

## Quick Start

```python
# 1. Create and start an agent defined in botcore.toml
await agent_create(name="researcher")
await agent_start(name="researcher")

# 2. Assign a task
result = await task_assign(description="Find performance issues", agent="researcher")
print(result)  # {"task_id": "...", "status": "completed", "result": "..."}

# 3. Check status
await agent_status(name="researcher")
await agent_heartbeat(name="researcher")

# 4. Clean up
await agent_stop(name="researcher")
```

## Configuration

```toml
[tool.botcore.plugins.agents]
default_model = "gpt-4.1"
max_agents = 10

[tool.botcore.plugins.agents.agents.researcher]
name = "researcher"
model = "gpt-4.1"
skills = ["dev_test", "dev_lint"]
max_concurrent_tasks = 2
system_prompt = "You are a research agent."
```
"""
