"""Tests for agent configuration models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from botcore_agents.config import AgentConfig, AgentsPluginConfig, get_agents_config


class TestAgentConfig:
    def test_defaults(self):
        cfg = AgentConfig()
        assert cfg.name == ""
        assert cfg.model == ""
        assert cfg.skills == []
        assert cfg.connectors == []
        assert cfg.memory_scope == "session"
        assert cfg.max_concurrent_tasks == 1
        assert cfg.heartbeat_interval == 30
        assert cfg.system_prompt == ""
        assert cfg.is_lead is False

    def test_valid_config(self):
        cfg = AgentConfig(
            name="researcher",
            model="gpt-4.1",
            skills=["dev_test", "dev_lint"],
            memory_scope="agent",
            max_concurrent_tasks=3,
            heartbeat_interval=60,
            system_prompt="You are a research agent.",
            is_lead=True,
        )
        assert cfg.name == "researcher"
        assert cfg.max_concurrent_tasks == 3
        assert cfg.is_lead is True

    def test_max_concurrent_tasks_bounds(self):
        with pytest.raises(ValidationError):
            AgentConfig(max_concurrent_tasks=0)
        with pytest.raises(ValidationError):
            AgentConfig(max_concurrent_tasks=11)

    def test_heartbeat_interval_bounds(self):
        with pytest.raises(ValidationError):
            AgentConfig(heartbeat_interval=4)
        with pytest.raises(ValidationError):
            AgentConfig(heartbeat_interval=301)

    def test_invalid_memory_scope(self):
        with pytest.raises(ValidationError):
            AgentConfig(memory_scope="invalid")

    def test_connector_commands_default(self):
        cfg = AgentConfig()
        assert cfg.connector_commands == []

    def test_connector_commands_set(self):
        cfg = AgentConfig(connector_commands=["github_issue_list", "github_pr_list"])
        assert cfg.connector_commands == ["github_issue_list", "github_pr_list"]

    def test_connectors_wildcard(self):
        cfg = AgentConfig(connectors=["*"])
        assert cfg.connectors == ["*"]

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            AgentConfig(unknown_field="value")


class TestAgentsPluginConfig:
    def test_defaults(self):
        cfg = AgentsPluginConfig()
        assert cfg.agents == {}
        assert cfg.default_model == "gpt-4.1"
        assert cfg.max_agents == 10

    def test_with_agents(self):
        cfg = AgentsPluginConfig(
            agents={
                "researcher": AgentConfig(name="researcher", model="gpt-4.1"),
                "coder": AgentConfig(name="coder", model="gpt-4.1"),
            },
            default_model="gpt-4.1-mini",
            max_agents=5,
        )
        assert len(cfg.agents) == 2
        assert "researcher" in cfg.agents
        assert cfg.max_agents == 5

    def test_max_agents_bounds(self):
        with pytest.raises(ValidationError):
            AgentsPluginConfig(max_agents=0)
        with pytest.raises(ValidationError):
            AgentsPluginConfig(max_agents=101)

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            AgentsPluginConfig(unknown_field="value")


class TestGetAgentsConfig:
    def test_none_returns_defaults(self):
        cfg = get_agents_config(None)
        assert isinstance(cfg, AgentsPluginConfig)
        assert cfg.agents == {}

    def test_dict_validates(self):
        raw = {
            "default_model": "gpt-4.1-mini",
            "agents": {
                "worker": {"name": "worker", "model": "gpt-4.1"},
            },
        }
        cfg = get_agents_config(raw)
        assert cfg.default_model == "gpt-4.1-mini"
        assert "worker" in cfg.agents

    def test_invalid_dict_raises(self):
        with pytest.raises(ValidationError):
            get_agents_config({"max_agents": -1})
