"""Tests for orchestrator state serialization: snapshot model, JSON backend, save/load."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from botcore_agents.config import AgentConfig, AgentsPluginConfig
from botcore_agents.models import AgentHealth, AgentState, Task
from botcore_agents.orchestrator import AgentOrchestrator
from botcore_agents.state import JsonStateBackend, OrchestratorSnapshot

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_config() -> AgentsPluginConfig:
    return AgentsPluginConfig(
        agents={
            "researcher": AgentConfig(
                name="researcher",
                role="researcher",
                model="gpt-4.1",
            ),
        },
    )


def _minimal_snapshot() -> OrchestratorSnapshot:
    config = _minimal_config()
    agent_state = AgentState(
        config=config.agents["researcher"],
        health=AgentHealth(name="researcher", status="idle"),
        session_id="sess-1",
    )
    task = Task(description="test task", status="completed", assigned_agent="researcher")
    return OrchestratorSnapshot(
        config=config,
        agents={"researcher": agent_state},
        tasks={task.id: task},
    )


# ===========================================================================
# TestOrchestratorSnapshot
# ===========================================================================


class TestOrchestratorSnapshot:
    def test_defaults(self):
        config = _minimal_config()
        snap = OrchestratorSnapshot(config=config, agents={}, tasks={})
        assert snap.version == "1.0"
        assert isinstance(snap.timestamp, datetime)
        assert snap.timestamp.tzinfo is not None

    def test_roundtrip_json(self):
        snap = _minimal_snapshot()
        raw = snap.model_dump(mode="json")
        restored = OrchestratorSnapshot.model_validate(raw)
        assert restored.version == snap.version
        assert restored.agents.keys() == snap.agents.keys()
        assert restored.tasks.keys() == snap.tasks.keys()

    def test_extra_fields_forbidden(self):
        config = _minimal_config()
        with pytest.raises(ValidationError):
            OrchestratorSnapshot(config=config, agents={}, tasks={}, bogus="nope")


# ===========================================================================
# TestJsonStateBackend
# ===========================================================================


class TestJsonStateBackend:
    @pytest.mark.asyncio
    async def test_save_creates_file(self, tmp_path: Path):
        path = tmp_path / "state.json"
        backend = JsonStateBackend(path)
        snap = _minimal_snapshot()
        await backend.save(snap)
        assert path.exists()
        content = path.read_text()
        assert '"version"' in content

    @pytest.mark.asyncio
    async def test_load_missing_file_returns_none(self, tmp_path: Path):
        path = tmp_path / "nope.json"
        backend = JsonStateBackend(path)
        result = await backend.load()
        assert result is None

    @pytest.mark.asyncio
    async def test_save_load_roundtrip(self, tmp_path: Path):
        path = tmp_path / "state.json"
        backend = JsonStateBackend(path)
        snap = _minimal_snapshot()
        await backend.save(snap)
        restored = await backend.load()
        assert restored is not None
        assert restored.version == snap.version
        assert set(restored.agents.keys()) == set(snap.agents.keys())
        assert set(restored.tasks.keys()) == set(snap.tasks.keys())

    @pytest.mark.asyncio
    async def test_stale_snapshot_returns_none(self, tmp_path: Path):
        path = tmp_path / "state.json"
        backend = JsonStateBackend(path, retention_hours=1)
        snap = _minimal_snapshot()
        # Force old timestamp
        snap.timestamp = datetime.now(UTC) - timedelta(hours=2)
        # Write manually to bypass save() which would re-timestamp
        path.write_text(snap.model_dump_json(indent=2))
        result = await backend.load()
        assert result is None

    @pytest.mark.asyncio
    async def test_custom_retention_hours(self, tmp_path: Path):
        path = tmp_path / "state.json"
        backend = JsonStateBackend(path, retention_hours=500)
        snap = _minimal_snapshot()
        snap.timestamp = datetime.now(UTC) - timedelta(hours=400)
        path.write_text(snap.model_dump_json(indent=2))
        result = await backend.load()
        assert result is not None

    @pytest.mark.asyncio
    async def test_save_creates_parent_directories(self, tmp_path: Path):
        path = tmp_path / "sub" / "dir" / "state.json"
        backend = JsonStateBackend(path)
        snap = _minimal_snapshot()
        await backend.save(snap)
        assert path.exists()

    @pytest.mark.asyncio
    async def test_atomic_write_cleans_up_temp_on_error(self, tmp_path: Path):
        path = tmp_path / "state.json"
        backend = JsonStateBackend(path)
        snap = _minimal_snapshot()

        # Patch os.replace to raise, simulating write failure
        with patch("botcore_agents.state.os.replace", side_effect=OSError("disk full")):
            with pytest.raises(OSError, match="disk full"):
                await backend.save(snap)

        # No temp files should remain
        remaining = list(tmp_path.glob("*.tmp"))
        assert remaining == []
        assert not path.exists()


# ===========================================================================
# TestOrchestratorSaveLoad
# ===========================================================================


class TestOrchestratorSaveLoad:
    @pytest.mark.asyncio
    async def test_save_no_backend_returns_error(self):
        orch = AgentOrchestrator(_minimal_config())
        result = await orch.save_state()
        assert not result.success
        assert result.error.code == "NO_BACKEND"

    @pytest.mark.asyncio
    async def test_load_no_backend_returns_error(self):
        orch = AgentOrchestrator(_minimal_config())
        result = await orch.load_state()
        assert not result.success
        assert result.error.code == "NO_BACKEND"

    @pytest.mark.asyncio
    async def test_full_roundtrip(self, tmp_path: Path):
        """Create agents, save, reset orchestrator, load, verify."""
        backend = JsonStateBackend(tmp_path / "state.json")
        config = _minimal_config()
        orch = AgentOrchestrator(config, backend=backend)

        # Create an agent manually (skip LLM)
        agent_cfg = config.agents["researcher"]
        health = AgentHealth(name="researcher", status="idle")
        orch._agents["researcher"] = AgentState(
            config=agent_cfg, health=health, session_id="live-session"
        )
        task = Task(description="do stuff", status="completed", assigned_agent="researcher")
        orch._tasks[task.id] = task

        # Save
        save_result = await orch.save_state()
        assert save_result.success
        assert save_result.data["saved"] is True
        assert save_result.data["agents"] == 1
        assert save_result.data["tasks"] == 1

        # Create a fresh orchestrator, load into it
        orch2 = AgentOrchestrator(_minimal_config(), backend=backend)
        load_result = await orch2.load_state()
        assert load_result.success
        assert load_result.data["restored"] is True
        assert load_result.data["agents"] == 1
        assert "researcher" in orch2._agents
        assert task.id in orch2._tasks

    @pytest.mark.asyncio
    async def test_loaded_agents_are_stopped(self, tmp_path: Path):
        backend = JsonStateBackend(tmp_path / "state.json")
        config = _minimal_config()
        orch = AgentOrchestrator(config, backend=backend)

        agent_cfg = config.agents["researcher"]
        health = AgentHealth(name="researcher", status="busy", current_task="t1")
        orch._agents["researcher"] = AgentState(
            config=agent_cfg,
            health=health,
            session_id="sess-x",
            active_tasks=["t1"],
            started_at=datetime.now(UTC),
        )

        await orch.save_state()

        orch2 = AgentOrchestrator(_minimal_config(), backend=backend)
        await orch2.load_state()

        state = orch2._agents["researcher"]
        assert state.health.status == "stopped"
        assert state.session_id == ""
        assert state.active_tasks == []
        assert state.health.current_task == ""
        assert state.started_at is None

    @pytest.mark.asyncio
    async def test_load_no_saved_state(self, tmp_path: Path):
        backend = JsonStateBackend(tmp_path / "nope.json")
        orch = AgentOrchestrator(_minimal_config(), backend=backend)
        result = await orch.load_state()
        assert result.success
        assert result.data["restored"] is False

    @pytest.mark.asyncio
    async def test_snapshot_deep_copies(self, tmp_path: Path):
        """Mutating live state after save should not affect snapshot."""
        backend = JsonStateBackend(tmp_path / "state.json")
        config = _minimal_config()
        orch = AgentOrchestrator(config, backend=backend)

        agent_cfg = config.agents["researcher"]
        health = AgentHealth(name="researcher", status="idle")
        orch._agents["researcher"] = AgentState(config=agent_cfg, health=health)

        await orch.save_state()

        # Mutate live state
        orch._agents["researcher"].health.tasks_completed = 999

        # Load into fresh orchestrator
        orch2 = AgentOrchestrator(_minimal_config(), backend=backend)
        await orch2.load_state()
        assert orch2._agents["researcher"].health.tasks_completed == 0

    @pytest.mark.asyncio
    async def test_backend_save_exception(self):
        mock_backend = AsyncMock()
        mock_backend.save.side_effect = OSError("boom")
        orch = AgentOrchestrator(_minimal_config(), backend=mock_backend)
        result = await orch.save_state()
        assert not result.success
        assert result.error.code == "STATE_SAVE_ERROR"

    @pytest.mark.asyncio
    async def test_backend_load_exception(self):
        mock_backend = AsyncMock()
        mock_backend.load.side_effect = OSError("boom")
        orch = AgentOrchestrator(_minimal_config(), backend=mock_backend)
        result = await orch.load_state()
        assert not result.success
        assert result.error.code == "STATE_LOAD_ERROR"
