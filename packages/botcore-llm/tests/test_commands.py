"""Tests for LLM commands (with mocked Copilot client)."""

from __future__ import annotations

import pytest
from afd.testing import assert_error, assert_success

from botcore_llm.commands import (
    llm_chat,
    llm_model_list,
    llm_session_create,
    llm_session_destroy,
    llm_session_list,
    set_config,
)
from botcore_llm.config import LlmConfig, LlmPermissionsConfig
from botcore_llm.session import get_session_registry


@pytest.fixture(autouse=True)
def _clean_registry():
    """Ensure a clean session registry for each test."""
    registry = get_session_registry()
    registry._sessions.clear()
    yield
    registry._sessions.clear()


class TestLlmSessionCreate:
    @pytest.mark.asyncio
    async def test_returns_session_id(self, patch_client_manager, mock_copilot_session):
        result = await llm_session_create(model="gpt-4.1")

        data = assert_success(result)
        assert data["session_id"] == mock_copilot_session.session_id
        assert data["model"] == "gpt-4.1"

    @pytest.mark.asyncio
    async def test_registers_in_session_registry(self, patch_client_manager, mock_copilot_session):
        await llm_session_create()

        registry = get_session_registry()
        entry = registry.get(mock_copilot_session.session_id)
        assert entry is not None
        assert entry.model == "gpt-4.1"

    @pytest.mark.asyncio
    async def test_uses_config_default_model(self, patch_client_manager, mock_copilot_session):
        set_config(LlmConfig(default_model="claude-sonnet-4.5"))
        try:
            result = await llm_session_create()

            data = assert_success(result)
            assert data["model"] == "claude-sonnet-4.5"
        finally:
            set_config(LlmConfig())  # reset

    @pytest.mark.asyncio
    async def test_uses_global_default_permissions_when_not_provided(
        self, patch_client_manager, mock_copilot_session
    ):
        default_permissions = LlmPermissionsConfig(
            allow_shell=True,
            allow_filesystem=True,
            allow_mcp=False,
            allow_custom_tools=False,
        )
        set_config(LlmConfig(permissions=default_permissions))
        try:
            await llm_session_create(model="gpt-4.1")

            registry = get_session_registry()
            entry = registry.get(mock_copilot_session.session_id)
            assert entry is not None
            handler = entry.config["on_permission_request"]

            assert handler({"kind": "shell"}, {})["kind"] == "approved"
            assert handler({"kind": "read", "path": "/tmp/x"}, {})["kind"] == "approved"
            assert handler({"kind": "mcp"}, {})["kind"] == "denied-by-rules"
            assert handler({"kind": "custom-tool"}, {})["kind"] == "denied-by-rules"
        finally:
            set_config(LlmConfig())


class TestLlmSessionDestroy:
    @pytest.mark.asyncio
    async def test_destroys_session(self, patch_client_manager, mock_copilot_session):
        await llm_session_create()

        result = await llm_session_destroy(mock_copilot_session.session_id)

        data = assert_success(result)
        assert data["status"] == "destroyed"
        mock_copilot_session.destroy.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_removes_from_registry(self, patch_client_manager, mock_copilot_session):
        await llm_session_create()
        await llm_session_destroy(mock_copilot_session.session_id)

        registry = get_session_registry()
        assert registry.get(mock_copilot_session.session_id) is None

    @pytest.mark.asyncio
    async def test_nonexistent_session_returns_error(self, patch_client_manager):
        result = await llm_session_destroy("no-such-session")

        assert_error(result, "SESSION_NOT_FOUND")


class TestLlmSessionList:
    @pytest.mark.asyncio
    async def test_returns_registered_sessions(self, patch_client_manager, mock_copilot_session):
        await llm_session_create(model="gpt-4.1")

        result = await llm_session_list()

        data = assert_success(result)
        assert len(data) == 1
        assert data[0]["session_id"] == mock_copilot_session.session_id

    @pytest.mark.asyncio
    async def test_empty_when_no_sessions(self, patch_client_manager):
        result = await llm_session_list()

        assert_success(result) == []


class TestLlmModelList:
    @pytest.mark.asyncio
    async def test_returns_model_info(self, patch_client_manager, mock_copilot_client):
        result = await llm_model_list()

        data = assert_success(result)
        assert len(data) == 1
        assert data[0]["id"] == "gpt-4.1"
        assert data[0]["supports_vision"] is True


class TestLlmChat:
    @pytest.mark.asyncio
    async def test_returns_assistant_response(self, patch_client_manager, mock_copilot_session):
        await llm_session_create()

        result = await llm_chat(
            session_id=mock_copilot_session.session_id,
            message="What is 2+2?",
        )

        data = assert_success(result)
        assert data["content"] == "Hello from the assistant"
        assert data["session_id"] == mock_copilot_session.session_id

    @pytest.mark.asyncio
    async def test_invalid_session_returns_error(self, patch_client_manager):
        result = await llm_chat(session_id="bad-id", message="hi")

        assert_error(result, "SESSION_NOT_FOUND")

    @pytest.mark.asyncio
    async def test_passes_attachments(self, patch_client_manager, mock_copilot_session):
        await llm_session_create()

        attachments = [{"type": "file", "path": "/tmp/test.txt", "displayName": "test.txt"}]
        await llm_chat(
            session_id=mock_copilot_session.session_id,
            message="Read this",
            attachments=attachments,
        )

        call_args = mock_copilot_session.send_and_wait.call_args[0][0]
        assert call_args["attachments"] == attachments
