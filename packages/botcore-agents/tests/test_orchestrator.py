"""Tests for the agent orchestrator."""

from __future__ import annotations

from botcore_agents.orchestrator import AgentOrchestrator, get_orchestrator, reset_orchestrator


class TestCreateAgent:
    async def test_create_configured_agent(self, orchestrator: AgentOrchestrator):
        result = await orchestrator.create_agent("researcher")
        assert result.success
        assert result.data["name"] == "researcher"
        assert result.data["status"] == "stopped"

    async def test_create_unconfigured_agent(self, orchestrator: AgentOrchestrator):
        result = await orchestrator.create_agent("unknown")
        assert not result.success
        assert result.error.code == "AGENT_NOT_CONFIGURED"

    async def test_create_duplicate_agent(self, orchestrator: AgentOrchestrator):
        await orchestrator.create_agent("researcher")
        result = await orchestrator.create_agent("researcher")
        assert not result.success
        assert result.error.code == "AGENT_ALREADY_EXISTS"

    async def test_create_respects_max_agents(self, orchestrator: AgentOrchestrator):
        # Config has max_agents=5, but only 2 agent configs
        await orchestrator.create_agent("researcher")
        await orchestrator.create_agent("coder")
        # Both slots used, third would need to be configured anyway
        result = await orchestrator.create_agent("nonexistent")
        assert not result.success
        assert result.error.code == "AGENT_NOT_CONFIGURED"


class TestStartAgent:
    async def test_start_agent_happy_path(self, orchestrator: AgentOrchestrator, mock_llm):
        await orchestrator.create_agent("researcher")
        result = await orchestrator.start_agent("researcher")
        assert result.success
        assert result.data["status"] == "idle"
        assert result.data["session_id"] == "session-agent-001"

    async def test_start_nonexistent_agent(self, orchestrator: AgentOrchestrator, mock_llm):
        result = await orchestrator.start_agent("ghost")
        assert not result.success
        assert result.error.code == "AGENT_NOT_FOUND"

    async def test_double_start(self, orchestrator: AgentOrchestrator, mock_llm):
        await orchestrator.create_agent("researcher")
        await orchestrator.start_agent("researcher")
        result = await orchestrator.start_agent("researcher")
        assert not result.success
        assert result.error.code == "AGENT_ALREADY_STARTED"

    async def test_start_uses_config_model(self, orchestrator: AgentOrchestrator, mock_llm):
        await orchestrator.create_agent("researcher")
        await orchestrator.start_agent("researcher")
        mock_llm["session_create"].assert_awaited_once_with(
            model="gpt-4.1",
            tools=["dev_test", "dev_lint"],
            system_prompt="You are a research agent.",
        )


class TestStopAgent:
    async def test_stop_agent_happy_path(self, orchestrator: AgentOrchestrator, mock_llm):
        await orchestrator.create_agent("researcher")
        await orchestrator.start_agent("researcher")
        result = await orchestrator.stop_agent("researcher")
        assert result.success
        assert result.data["status"] == "stopped"
        mock_llm["session_destroy"].assert_awaited_once()

    async def test_stop_nonexistent(self, orchestrator: AgentOrchestrator, mock_llm):
        result = await orchestrator.stop_agent("ghost")
        assert not result.success
        assert result.error.code == "AGENT_NOT_FOUND"

    async def test_stop_already_stopped(self, orchestrator: AgentOrchestrator, mock_llm):
        await orchestrator.create_agent("researcher")
        result = await orchestrator.stop_agent("researcher")
        assert not result.success
        assert result.error.code == "AGENT_NOT_STARTED"


class TestAssignTask:
    async def test_assign_task_happy_path(self, orchestrator: AgentOrchestrator, mock_llm):
        await orchestrator.create_agent("researcher")
        await orchestrator.start_agent("researcher")
        result = await orchestrator.assign_task("Find bugs", agent="researcher")
        assert result.success
        assert result.data["status"] == "completed"
        assert result.data["result"] == "Task completed successfully"
        assert result.data["agent"] == "researcher"

    async def test_assign_to_stopped_agent(self, orchestrator: AgentOrchestrator, mock_llm):
        await orchestrator.create_agent("researcher")
        result = await orchestrator.assign_task("Do work", agent="researcher")
        assert not result.success
        assert result.error.code == "AGENT_NOT_STARTED"

    async def test_assign_to_nonexistent_agent(self, orchestrator: AgentOrchestrator, mock_llm):
        result = await orchestrator.assign_task("Do work", agent="ghost")
        assert not result.success
        assert result.error.code == "AGENT_NOT_FOUND"

    async def test_assign_at_capacity(self, orchestrator: AgentOrchestrator, mock_llm):
        """Coder has max_concurrent_tasks=1; simulate already busy."""
        await orchestrator.create_agent("coder")
        await orchestrator.start_agent("coder")

        # Manually add a task to simulate busy state
        state = orchestrator._agents["coder"]
        state.active_tasks.append("fake-task-id")

        result = await orchestrator.assign_task("More work", agent="coder")
        assert not result.success
        assert result.error.code == "AGENT_AT_CAPACITY"

    async def test_assign_respects_priority(self, orchestrator: AgentOrchestrator, mock_llm):
        await orchestrator.create_agent("researcher")
        await orchestrator.start_agent("researcher")
        result = await orchestrator.assign_task("Urgent", agent="researcher", priority=1)
        assert result.success
        task_id = result.data["task_id"]
        task_result = orchestrator.get_task(task_id)
        assert task_result.data["priority"] == 1

    async def test_agent_returns_idle_after_task(
        self, orchestrator: AgentOrchestrator, mock_llm
    ):
        await orchestrator.create_agent("researcher")
        await orchestrator.start_agent("researcher")
        await orchestrator.assign_task("Do something", agent="researcher")
        status = orchestrator.get_agent_status("researcher")
        assert status.data["status"] == "idle"

    async def test_failed_chat_marks_task_failed(self, orchestrator: AgentOrchestrator, mock_llm):
        from afd import error

        mock_llm["chat"].return_value = error("CHAT_ERROR", "LLM failed")

        await orchestrator.create_agent("researcher")
        await orchestrator.start_agent("researcher")
        result = await orchestrator.assign_task("Bad task", agent="researcher")
        assert not result.success
        assert result.error.code == "TASK_EXECUTION_ERROR"

    async def test_assign_no_target_returns_error(self, orchestrator: AgentOrchestrator):
        result = await orchestrator.assign_task("Do work")
        assert not result.success
        assert result.error.code == "NO_TARGET"


class TestGetAgentStatus:
    async def test_status_stopped(self, orchestrator: AgentOrchestrator):
        await orchestrator.create_agent("researcher")
        result = orchestrator.get_agent_status("researcher")
        assert result.success
        assert result.data["status"] == "stopped"

    async def test_status_idle(self, orchestrator: AgentOrchestrator, mock_llm):
        await orchestrator.create_agent("researcher")
        await orchestrator.start_agent("researcher")
        result = orchestrator.get_agent_status("researcher")
        assert result.success
        assert result.data["status"] == "idle"
        assert result.data["uptime_seconds"] >= 0

    async def test_status_nonexistent(self, orchestrator: AgentOrchestrator):
        result = orchestrator.get_agent_status("ghost")
        assert not result.success
        assert result.error.code == "AGENT_NOT_FOUND"


class TestGetTask:
    async def test_get_task(self, orchestrator: AgentOrchestrator, mock_llm):
        await orchestrator.create_agent("researcher")
        await orchestrator.start_agent("researcher")
        assign_result = await orchestrator.assign_task("Work", agent="researcher")
        task_id = assign_result.data["task_id"]

        result = orchestrator.get_task(task_id)
        assert result.success
        assert result.data["description"] == "Work"
        assert result.data["status"] == "completed"

    def test_get_nonexistent_task(self, orchestrator: AgentOrchestrator):
        result = orchestrator.get_task("no-such-id")
        assert not result.success
        assert result.error.code == "TASK_NOT_FOUND"


class TestHeartbeat:
    async def test_heartbeat_updates_timestamp(self, orchestrator: AgentOrchestrator, mock_llm):
        await orchestrator.create_agent("researcher")
        await orchestrator.start_agent("researcher")
        result = orchestrator.heartbeat("researcher")
        assert result.success
        assert result.data["last_heartbeat"] is not None

    async def test_heartbeat_stopped_agent(self, orchestrator: AgentOrchestrator):
        await orchestrator.create_agent("researcher")
        result = orchestrator.heartbeat("researcher")
        assert not result.success
        assert result.error.code == "AGENT_NOT_STARTED"

    def test_heartbeat_nonexistent(self, orchestrator: AgentOrchestrator):
        result = orchestrator.heartbeat("ghost")
        assert not result.success
        assert result.error.code == "AGENT_NOT_FOUND"


class TestSingleton:
    def test_get_orchestrator_creates_default(self):
        orch = get_orchestrator()
        assert isinstance(orch, AgentOrchestrator)

    def test_get_orchestrator_returns_same(self):
        orch1 = get_orchestrator()
        orch2 = get_orchestrator()
        assert orch1 is orch2

    def test_reset_orchestrator(self):
        orch1 = get_orchestrator()
        reset_orchestrator()
        orch2 = get_orchestrator()
        assert orch1 is not orch2


class TestRoleBasedPooling:
    """Role-based agent spawning: assign by role, auto-scale instances."""

    async def test_assign_by_role_reuses_idle_agent(
        self, orchestrator: AgentOrchestrator, mock_llm
    ):
        """If an idle agent with the role exists, reuse it."""
        await orchestrator.create_agent("researcher")
        await orchestrator.start_agent("researcher")
        result = await orchestrator.assign_task("Find bugs", role="researcher")
        assert result.success
        assert result.data["agent"] == "researcher"

    async def test_assign_by_role_spawns_when_busy(self, orchestrator: AgentOrchestrator, mock_llm):
        """If the existing role agent is busy, spawn a new instance."""
        from afd import success

        call_count = 0

        async def varying_session_create(**kwargs):
            nonlocal call_count
            call_count += 1
            return success(
                data={
                    "session_id": f"session-{call_count:03d}",
                    "model": kwargs.get("model", "gpt-4.1"),
                    "tools": [],
                },
                reasoning="Mock session",
            )

        mock_llm["session_create"].side_effect = varying_session_create

        await orchestrator.create_agent("researcher")
        await orchestrator.start_agent("researcher")

        # Make the first instance busy
        state = orchestrator._agents["researcher"]
        state.active_tasks.append("fake-task-id")
        state.active_tasks.append("fake-task-id-2")  # researcher has max_concurrent_tasks=2
        state.health.status = "busy"

        result = await orchestrator.assign_task("Second task", role="researcher")
        assert result.success
        # Should have spawned researcher-1
        assert result.data["agent"] == "researcher-1"
        assert "researcher-1" in orchestrator.agents

    async def test_assign_by_role_spawns_sequential_names(
        self, orchestrator: AgentOrchestrator, mock_llm
    ):
        """Spawned instances get sequential names: role-1, role-2, etc."""
        from afd import success

        call_count = 0

        async def varying_session_create(**kwargs):
            nonlocal call_count
            call_count += 1
            return success(
                data={
                    "session_id": f"session-{call_count:03d}",
                    "model": kwargs.get("model", "gpt-4.1"),
                    "tools": [],
                },
                reasoning="Mock session",
            )

        mock_llm["session_create"].side_effect = varying_session_create

        await orchestrator.create_agent("researcher")
        await orchestrator.start_agent("researcher")

        # Fill researcher to capacity
        state = orchestrator._agents["researcher"]
        state.active_tasks.extend(["t1", "t2"])
        state.health.status = "busy"

        # Spawn researcher-1
        r1 = await orchestrator.assign_task("Task A", role="researcher")
        assert r1.success
        assert r1.data["agent"] == "researcher-1"

        # Fill researcher-1 to capacity
        state1 = orchestrator._agents["researcher-1"]
        state1.active_tasks.extend(["t3", "t4"])
        state1.health.status = "busy"

        # Spawn researcher-2
        r2 = await orchestrator.assign_task("Task B", role="researcher")
        assert r2.success
        assert r2.data["agent"] == "researcher-2"

    async def test_assign_by_role_unconfigured(self, orchestrator: AgentOrchestrator, mock_llm):
        """Role with no matching config returns error."""
        result = await orchestrator.assign_task("Work", role="unknown")
        assert not result.success
        assert result.error.code == "ROLE_NOT_CONFIGURED"

    async def test_assign_by_role_pool_full(self, orchestrator: AgentOrchestrator, mock_llm):
        """When pool hits max_agents and all role agents are busy, return error."""
        from afd import success

        call_count = 0

        async def varying_session_create(**kwargs):
            nonlocal call_count
            call_count += 1
            return success(
                data={
                    "session_id": f"session-{call_count:03d}",
                    "model": kwargs.get("model", "gpt-4.1"),
                    "tools": [],
                },
                reasoning="Mock session",
            )

        mock_llm["session_create"].side_effect = varying_session_create

        # Config has max_agents=5. Fill up the pool.
        await orchestrator.create_agent("researcher")
        await orchestrator.start_agent("researcher")
        await orchestrator.create_agent("coder")
        await orchestrator.start_agent("coder")

        # Make researcher busy
        orchestrator._agents["researcher"].active_tasks.extend(["t1", "t2"])
        orchestrator._agents["researcher"].health.status = "busy"

        # Spawn 3 more to hit max_agents=5
        for _ in range(3):
            result = await orchestrator.assign_task("Work", role="researcher")
            assert result.success
            spawned_name = result.data["agent"]
            orchestrator._agents[spawned_name].active_tasks.extend(["tx", "ty"])
            orchestrator._agents[spawned_name].health.status = "busy"

        # Pool is now full (5 agents), all researchers busy → should fail
        result = await orchestrator.assign_task("One more", role="researcher")
        assert not result.success
        assert result.error.code == "MAX_AGENTS_REACHED"

    async def test_spawned_agent_inherits_config(self, orchestrator: AgentOrchestrator, mock_llm):
        """Spawned instances get the same model, skills, and prompt as the template."""
        from afd import success

        call_count = 0
        captured_kwargs = []

        async def capturing_session_create(**kwargs):
            nonlocal call_count
            call_count += 1
            captured_kwargs.append(kwargs)
            return success(
                data={
                    "session_id": f"session-{call_count:03d}",
                    "model": kwargs.get("model", "gpt-4.1"),
                    "tools": [],
                },
                reasoning="Mock session",
            )

        mock_llm["session_create"].side_effect = capturing_session_create

        await orchestrator.create_agent("researcher")
        await orchestrator.start_agent("researcher")

        # Make busy
        orchestrator._agents["researcher"].active_tasks.extend(["t1", "t2"])
        orchestrator._agents["researcher"].health.status = "busy"

        await orchestrator.assign_task("Another task", role="researcher")

        # The spawned instance should have same config
        spawned = orchestrator._agents["researcher-1"]
        assert spawned.config.model == "gpt-4.1"
        assert spawned.config.skills == ["dev_test", "dev_lint"]
        assert spawned.config.system_prompt == "You are a research agent."
        assert spawned.config.role == "researcher"

    async def test_agent_preferred_over_role(self, orchestrator: AgentOrchestrator, mock_llm):
        """When both agent and role are provided, agent takes precedence."""
        await orchestrator.create_agent("researcher")
        await orchestrator.start_agent("researcher")
        result = await orchestrator.assign_task("Work", agent="researcher", role="coder")
        assert result.success
        assert result.data["agent"] == "researcher"
