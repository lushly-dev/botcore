"""Tests for agent command functions."""

from __future__ import annotations

import pytest

from botcore_agents.commands import (
    agent_create,
    agent_heartbeat,
    agent_start,
    agent_status,
    agent_stop,
    set_config,
    task_assign,
    task_status,
)
from botcore_agents.config import AgentsPluginConfig
from botcore_agents.orchestrator import reset_orchestrator


@pytest.fixture(autouse=True)
def _inject_config(sample_config: AgentsPluginConfig):
    """Inject sample config into the commands module for every test."""
    set_config(sample_config)
    reset_orchestrator()
    yield
    set_config(None)
    reset_orchestrator()


class TestAgentCreate:
    async def test_create_returns_success(self):
        result = await agent_create(name="researcher")
        assert result.success
        assert result.data["name"] == "researcher"
        assert result.data["status"] == "stopped"

    async def test_create_unconfigured_returns_error(self):
        result = await agent_create(name="unknown")
        assert not result.success
        assert result.error.code == "AGENT_NOT_CONFIGURED"


class TestAgentStart:
    async def test_start_returns_session(self, mock_llm):
        await agent_create(name="researcher")
        result = await agent_start(name="researcher")
        assert result.success
        assert result.data["session_id"] == "session-agent-001"

    async def test_start_not_found(self, mock_llm):
        result = await agent_start(name="ghost")
        assert not result.success
        assert result.error.code == "AGENT_NOT_FOUND"


class TestAgentStop:
    async def test_stop_returns_stopped(self, mock_llm):
        await agent_create(name="researcher")
        await agent_start(name="researcher")
        result = await agent_stop(name="researcher")
        assert result.success
        assert result.data["status"] == "stopped"

    async def test_stop_not_started(self, mock_llm):
        await agent_create(name="researcher")
        result = await agent_stop(name="researcher")
        assert not result.success
        assert result.error.code == "AGENT_NOT_STARTED"


class TestAgentStatus:
    async def test_status_returns_health(self, mock_llm):
        await agent_create(name="researcher")
        await agent_start(name="researcher")
        result = await agent_status(name="researcher")
        assert result.success
        assert result.data["name"] == "researcher"
        assert result.data["status"] == "idle"

    async def test_status_not_found(self):
        result = await agent_status(name="ghost")
        assert not result.success
        assert result.error.code == "AGENT_NOT_FOUND"


class TestAgentHeartbeat:
    async def test_heartbeat_updates(self, mock_llm):
        await agent_create(name="researcher")
        await agent_start(name="researcher")
        result = await agent_heartbeat(name="researcher")
        assert result.success
        assert result.data["last_heartbeat"] is not None

    async def test_heartbeat_not_started(self):
        await agent_create(name="researcher")
        result = await agent_heartbeat(name="researcher")
        assert not result.success
        assert result.error.code == "AGENT_NOT_STARTED"


class TestTaskAssign:
    async def test_assign_returns_result(self, mock_llm):
        await agent_create(name="researcher")
        await agent_start(name="researcher")
        result = await task_assign(description="Find bugs", agent="researcher")
        assert result.success
        assert result.data["status"] == "completed"
        assert result.data["result"] == "Task completed successfully"

    async def test_assign_custom_priority(self, mock_llm):
        await agent_create(name="researcher")
        await agent_start(name="researcher")
        result = await task_assign(description="Urgent", agent="researcher", priority=1)
        assert result.success
        task_id = result.data["task_id"]
        task_result = await task_status(task_id=task_id)
        assert task_result.data["priority"] == 1

    async def test_assign_not_found(self, mock_llm):
        result = await task_assign(description="Work", agent="ghost")
        assert not result.success
        assert result.error.code == "AGENT_NOT_FOUND"

    async def test_assign_by_role(self, mock_llm):
        await agent_create(name="researcher")
        await agent_start(name="researcher")
        result = await task_assign(description="Research task", role="researcher")
        assert result.success
        assert result.data["agent"] == "researcher"

    async def test_assign_no_target(self):
        result = await task_assign(description="Work")
        assert not result.success
        assert result.error.code == "NO_TARGET"


class TestTaskStatus:
    async def test_task_status_found(self, mock_llm):
        await agent_create(name="researcher")
        await agent_start(name="researcher")
        assign_result = await task_assign(description="Work", agent="researcher")
        task_id = assign_result.data["task_id"]
        result = await task_status(task_id=task_id)
        assert result.success
        assert result.data["description"] == "Work"

    async def test_task_status_not_found(self):
        result = await task_status(task_id="no-such-id")
        assert not result.success
        assert result.error.code == "TASK_NOT_FOUND"


# ---------------------------------------------------------------------------
# Integration scenarios
# ---------------------------------------------------------------------------


class TestHappyPathScenario:
    """End-to-end: create → start → assign → check status → stop."""

    async def test_full_lifecycle(self, mock_llm):
        # Create
        r = await agent_create(name="researcher")
        assert r.success

        # Start
        r = await agent_start(name="researcher")
        assert r.success
        session_id = r.data["session_id"]
        assert session_id

        # Assign task
        r = await task_assign(description="Analyse codebase", agent="researcher")
        assert r.success
        assert r.data["status"] == "completed"
        task_id = r.data["task_id"]

        # Check task status
        r = await task_status(task_id=task_id)
        assert r.success
        assert r.data["status"] == "completed"
        assert r.data["assigned_agent"] == "researcher"

        # Check agent health
        r = await agent_status(name="researcher")
        assert r.success
        assert r.data["tasks_completed"] == 1

        # Stop
        r = await agent_stop(name="researcher")
        assert r.success
        assert r.data["status"] == "stopped"


class TestMultiAgentIsolation:
    """Two agents with independent sessions."""

    async def test_two_agents_independent(self, mock_llm):
        # Second agent gets a different session ID
        from afd import success

        call_count = 0

        async def varying_session_create(**kwargs):
            nonlocal call_count
            call_count += 1
            return success(
                data={
                    "session_id": f"session-agent-{call_count:03d}",
                    "model": kwargs.get("model", "gpt-4.1"),
                    "tools": [],
                },
                reasoning="Mock session",
            )

        mock_llm["session_create"].side_effect = varying_session_create

        await agent_create(name="researcher")
        await agent_create(name="coder")
        await agent_start(name="researcher")
        await agent_start(name="coder")

        r1 = await agent_status(name="researcher")
        r2 = await agent_status(name="coder")
        assert r1.data["name"] == "researcher"
        assert r2.data["name"] == "coder"

        # Assign to each
        t1 = await task_assign(description="Research", agent="researcher")
        t2 = await task_assign(description="Code", agent="coder")
        assert t1.success
        assert t2.success
        assert t1.data["task_id"] != t2.data["task_id"]


class TestErrorCascading:
    """Stop agent with running task → task marked cancelled."""

    async def test_stop_cancels_active_tasks(self, mock_llm):
        await agent_create(name="researcher")
        await agent_start(name="researcher")

        # Simulate an active task without actually running it
        from botcore_agents.orchestrator import get_orchestrator

        orch = get_orchestrator()
        from botcore_agents.models import Task

        task = Task(description="Long running", assigned_agent="researcher", status="running")
        orch._tasks[task.id] = task
        orch._agents["researcher"].active_tasks.append(task.id)

        result = await agent_stop(name="researcher")
        assert result.success
        assert task.id in result.data["cancelled_tasks"]

        # Verify task is cancelled
        task_result = await task_status(task_id=task.id)
        assert task_result.data["status"] == "cancelled"


class TestCapacityLimit:
    """Assign tasks up to max_concurrent_tasks, next one errors."""

    async def test_capacity_enforcement(self, mock_llm):
        # Coder has max_concurrent_tasks=1
        await agent_create(name="coder")
        await agent_start(name="coder")

        # Manually fill capacity
        from botcore_agents.orchestrator import get_orchestrator

        orch = get_orchestrator()
        orch._agents["coder"].active_tasks.append("fake-task")

        result = await task_assign(description="More work", agent="coder")
        assert not result.success
        assert result.error.code == "AGENT_AT_CAPACITY"
