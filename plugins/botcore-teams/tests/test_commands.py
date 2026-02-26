"""Tests for command handlers."""

from __future__ import annotations

from botcore_teams.commands import teams_handle_card_action, teams_handle_message


class TestHandleMessage:
    async def test_assign_routing(self) -> None:
        result = await teams_handle_message(
            "assign research the latest Azure SDK changes to @researcher",
            user_id="u1",
            user_name="Alice",
            conversation_id="c1",
        )
        assert result.success is True
        assert result.data["agent"] == "researcher"
        assert "research the latest Azure SDK changes" in result.data["description"]

    async def test_team_status_routing(self) -> None:
        result = await teams_handle_message(
            "team status",
            user_id="u1",
            user_name="Alice",
            conversation_id="c1",
        )
        assert result.success is True
        assert "agents" in result.data

    async def test_task_status_routing(self) -> None:
        result = await teams_handle_message(
            "status of task-001",
            user_id="u1",
            user_name="Alice",
            conversation_id="c1",
        )
        assert result.success is True
        assert "status" in result.data

    async def test_cancel_routing(self) -> None:
        result = await teams_handle_message(
            "cancel task-001",
            user_id="u1",
            user_name="Alice",
            conversation_id="c1",
        )
        assert result.success is True
        assert result.data["cancelled"] is True

    async def test_list_tasks_routing(self) -> None:
        result = await teams_handle_message(
            "list tasks",
            user_id="u1",
            user_name="Alice",
            conversation_id="c1",
        )
        assert result.success is True
        assert "tasks" in result.data

    async def test_unknown_intent_error(self) -> None:
        result = await teams_handle_message(
            "hello there nice weather",
            user_id="u1",
            user_name="Alice",
            conversation_id="c1",
        )
        assert result.success is False
        assert result.error.code == "UNKNOWN_INTENT"


class TestHandleCardAction:
    async def test_retry_action(self) -> None:
        result = await teams_handle_card_action(
            "retry",
            {"original_text": "team status"},
            user_id="u1",
        )
        assert result.success is True
        assert "agents" in result.data

    async def test_followup_action(self) -> None:
        result = await teams_handle_card_action(
            "followup",
            {"text": "list tasks"},
            user_id="u1",
        )
        assert result.success is True
        assert "tasks" in result.data

    async def test_retry_missing_text(self) -> None:
        result = await teams_handle_card_action("retry", {}, user_id="u1")
        assert result.success is False
        assert result.error.code == "MISSING_CONTEXT"

    async def test_unknown_action(self) -> None:
        result = await teams_handle_card_action("bogus", {}, user_id="u1")
        assert result.success is False
        assert result.error.code == "UNKNOWN_ACTION"
