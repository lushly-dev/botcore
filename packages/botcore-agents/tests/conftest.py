"""Shared test fixtures for botcore-agents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from botcore_agents.config import AgentConfig, AgentsPluginConfig
from botcore_agents.orchestrator import AgentOrchestrator, reset_orchestrator

# ---------------------------------------------------------------------------
# Lightweight stubs — avoid importing copilot at collection time
# ---------------------------------------------------------------------------


@dataclass
class _MockEventData:
    content: str = "Task completed successfully"
    message_id: str = "msg-001"


@dataclass
class _MockSessionEvent:
    data: Any = None
    id: Any = None
    timestamp: Any = None
    type: Any = None


# ---------------------------------------------------------------------------
# Config fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_agent_config() -> AgentConfig:
    return AgentConfig(
        name="researcher",
        role="researcher",
        model="gpt-4.1",
        skills=["dev_test", "dev_lint"],
        max_concurrent_tasks=2,
        system_prompt="You are a research agent.",
    )


@pytest.fixture()
def sample_config(sample_agent_config: AgentConfig) -> AgentsPluginConfig:
    return AgentsPluginConfig(
        agents={
            "researcher": sample_agent_config,
            "coder": AgentConfig(
                name="coder",
                role="coder",
                model="gpt-4.1",
                skills=["dev_build"],
                max_concurrent_tasks=1,
            ),
        },
        default_model="gpt-4.1",
        max_agents=5,
    )


# ---------------------------------------------------------------------------
# Mock LLM fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_session_event() -> _MockSessionEvent:
    return _MockSessionEvent(data=_MockEventData())


@pytest.fixture()
def mock_llm_session_create():
    """Patch llm_session_create to return a fake session."""
    with patch(
        "botcore_agents.orchestrator.llm_session_create",
        new_callable=AsyncMock,
    ) as mock_create:
        from afd import success

        mock_create.return_value = success(
            data={
                "session_id": "session-agent-001",
                "model": "gpt-4.1",
                "tools": [],
            },
            reasoning="Mock session created",
        )
        yield mock_create


@pytest.fixture()
def mock_llm_session_destroy():
    """Patch llm_session_destroy."""
    with patch(
        "botcore_agents.orchestrator.llm_session_destroy",
        new_callable=AsyncMock,
    ) as mock_destroy:
        from afd import success

        mock_destroy.return_value = success(
            data={"session_id": "session-agent-001", "status": "destroyed"},
            reasoning="Mock session destroyed",
        )
        yield mock_destroy


@pytest.fixture()
def mock_llm_chat():
    """Patch llm_chat to return a fake response."""
    with patch(
        "botcore_agents.orchestrator.llm_chat",
        new_callable=AsyncMock,
    ) as mock_chat:
        from afd import success

        mock_chat.return_value = success(
            data={
                "session_id": "session-agent-001",
                "message_id": "msg-001",
                "content": "Task completed successfully",
            },
            reasoning="Mock chat response",
        )
        yield mock_chat


@pytest.fixture()
def mock_llm(mock_llm_session_create, mock_llm_session_destroy, mock_llm_chat):
    """Convenience fixture that patches all LLM commands."""
    return {
        "session_create": mock_llm_session_create,
        "session_destroy": mock_llm_session_destroy,
        "chat": mock_llm_chat,
    }


# ---------------------------------------------------------------------------
# Orchestrator fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def orchestrator(sample_config: AgentsPluginConfig) -> AgentOrchestrator:
    """Fresh orchestrator for each test."""
    return AgentOrchestrator(sample_config)


@pytest.fixture(autouse=True)
def _clean_orchestrator():
    """Reset the module-level singleton between tests."""
    reset_orchestrator()
    yield
    reset_orchestrator()
