"""Tests for agent task progress streaming (assign_task_stream / resume_task_stream)."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from afd import error
from afd.core.streaming import create_complete_chunk, create_data_chunk, create_progress_chunk
from afd.testing import assert_error, assert_success

import botcore_agents.commands as commands_mod
from botcore_agents.models import Task
from botcore_agents.orchestrator import AgentOrchestrator


async def _started(orchestrator: AgentOrchestrator, name: str = "researcher") -> None:
    await orchestrator.create_agent(name)
    await orchestrator.start_agent(name)


async def _collect(stream):
    return [chunk async for chunk in stream]


def _chat_stream(*pieces: str, hang: bool = False):
    """A fake llm_chat_stream that streams *pieces*, then completes or hangs."""

    async def fake(session_id, message, attachments=None, timeout=None):
        yield create_progress_chunk(0.0, message="Message sent", phase="send")
        yield create_progress_chunk(0.0, message="Running grep", phase="tool")
        for i, piece in enumerate(pieces):
            last = i == len(pieces) - 1 and not hang
            yield create_data_chunk({"text": piece, "message_id": "m1"}, index=i, is_last=last)
        if hang:
            await asyncio.Event().wait()
        content = "".join(pieces)
        data = {"session_id": session_id, "message_id": "m1", "content": content}
        yield create_complete_chunk(total_chunks=len(pieces), total_duration_ms=0, data=data)

    return patch("botcore_agents.task_stream.llm_chat_stream", fake)


class TestAssignTaskStream:
    async def test_streams_progress_text_and_result(self, orchestrator, mock_llm):
        await _started(orchestrator)
        with _chat_stream("Found ", "three ", "files"):
            chunks = await _collect(
                orchestrator.assign_task_stream("Find files", agent="researcher")
            )

        assert [c.type for c in chunks] == [
            "progress",
            "progress",
            "progress",
            "data",
            "data",
            "data",
            "complete",
        ]
        task_id = chunks[-1].data["task_id"]
        assert chunks[0].phase == "started"
        assert task_id in chunks[0].message and "researcher" in chunks[0].message
        assert [c.message for c in chunks[1:3]] == ["Message sent", "Running grep"]
        data = [c for c in chunks if c.type == "data"]
        assert [(c.data["text"], c.index, c.is_last) for c in data] == [
            ("Found ", 0, False),
            ("three ", 1, False),
            ("files", 2, True),
        ]
        assert {c.data["task_id"] for c in data} == {task_id}
        complete = chunks[-1]
        assert complete.total_chunks == 3
        assert complete.data == {
            "task_id": task_id,
            "status": "completed",
            "result": "Found three files",
            "agent": "researcher",
        }
        assert orchestrator.tasks[task_id].result == "Found three files"
        assert orchestrator.get_agent_status("researcher").data["status"] == "idle"

    async def test_role_resolution(self, orchestrator, mock_llm):
        chunks = await _collect(orchestrator.assign_task_stream("Research", role="researcher"))

        assert chunks[-1].type == "complete"
        assert chunks[-1].data["agent"].startswith("researcher")

    @pytest.mark.parametrize(
        ("kwargs", "code"),
        [({}, "NO_TARGET"), ({"agent": "ghost"}, "AGENT_NOT_FOUND")],
    )
    async def test_target_errors_create_no_task(self, orchestrator, mock_llm, kwargs, code):
        chunks = await _collect(orchestrator.assign_task_stream("Work", **kwargs))

        assert [c.type for c in chunks] == ["error"]
        assert chunks[0].error.code == code
        assert orchestrator.tasks == {}

    async def test_chat_failure_fails_the_task(self, orchestrator, mock_llm):
        mock_llm["chat"].return_value = error("CHAT_ERROR", "LLM failed")
        await _started(orchestrator)

        chunks = await _collect(orchestrator.assign_task_stream("Bad task", agent="researcher"))

        err = chunks[-1]
        assert err.type == "error"
        assert err.error.code == "TASK_EXECUTION_ERROR"
        assert "LLM failed" in err.error.message
        assert err.error.suggestion
        (task,) = orchestrator.tasks.values()
        assert task.status == "failed"
        health = orchestrator.get_agent_status("researcher").data
        assert health["status"] == "idle"
        assert health["tasks_failed"] == 1

    async def test_closing_early_cancels_the_task(self, orchestrator, mock_llm):
        await _started(orchestrator)
        with _chat_stream("partial", hang=True):
            stream = orchestrator.assign_task_stream("Long task", agent="researcher")
            async for chunk in stream:
                if chunk.type == "data":
                    break
            await stream.aclose()

        (task,) = orchestrator.tasks.values()
        assert task.status == "cancelled"
        assert task.completed_at is not None
        health = orchestrator.get_agent_status("researcher").data
        assert health["status"] == "idle"
        assert health["current_task"] == ""
        assert health["tasks_completed"] == 0
        assert health["tasks_failed"] == 0

    async def test_cancelling_the_consumer_cancels_the_task(self, orchestrator, mock_llm):
        await _started(orchestrator)
        seen = asyncio.Event()

        async def consume():
            async for chunk in orchestrator.assign_task_stream("Long task", agent="researcher"):
                if chunk.type == "data":
                    seen.set()

        with _chat_stream("partial", hang=True):
            task = asyncio.create_task(consume())
            await seen.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

        (record,) = orchestrator.tasks.values()
        assert record.status == "cancelled"
        assert orchestrator.get_agent_status("researcher").data["status"] == "idle"

    async def test_stopping_the_agent_mid_task(self, orchestrator, mock_llm):
        """stop_agent cancels the running task; the stream reports it, the agent stays stopped."""
        await _started(orchestrator)
        chunks = []

        async def consume():
            async for chunk in orchestrator.assign_task_stream("Long task", agent="researcher"):
                chunks.append(chunk)
                if chunk.type == "data":
                    await orchestrator.stop_agent("researcher")

        with _chat_stream("partial", "rest"):
            await consume()

        assert chunks[-1].type == "error"
        assert chunks[-1].error.code == "TASK_CANCELLED"
        assert chunks[-1].error.suggestion
        (task,) = orchestrator.tasks.values()
        assert task.status == "cancelled"
        assert orchestrator.get_agent_status("researcher").data["status"] == "stopped"

    async def test_agent_deleted_mid_task(self, orchestrator, mock_llm):
        """Stopping and deleting the agent mid-task still ends with a result, not a crash."""
        await _started(orchestrator)

        async def stop_and_delete_on_data():
            async for chunk in orchestrator.assign_task_stream("Long task", agent="researcher"):
                if chunk.type == "data":
                    await orchestrator.stop_agent("researcher")
                    await orchestrator.delete_agent("researcher")
            return chunk

        with _chat_stream("partial", "rest"):
            last = await stop_and_delete_on_data()

        assert last.type == "error"
        assert last.error.code == "TASK_CANCELLED"
        assert "researcher" not in orchestrator.agents

    async def test_replacement_agent_with_same_name_is_untouched(self, orchestrator, mock_llm):
        """Finishing an old task does not change a new agent created under the same name."""
        await _started(orchestrator)

        async def replace_on_data():
            async for chunk in orchestrator.assign_task_stream("Long task", agent="researcher"):
                if chunk.type == "data":
                    await orchestrator.stop_agent("researcher")
                    await orchestrator.delete_agent("researcher")
                    await _started(orchestrator)
                    replacement = orchestrator._agents["researcher"]
                    replacement.health.status = "busy"
                    replacement.health.current_task = "other"

        with _chat_stream("partial", "rest"):
            await replace_on_data()

        health = orchestrator.get_agent_status("researcher").data
        assert health["current_task"] == "other"
        assert health["status"] == "busy"

    async def test_closing_early_closes_the_chat_stream(self, orchestrator, mock_llm):
        await _started(orchestrator)
        closed = []

        async def chat(session_id, message, attachments=None, timeout=None):
            try:
                yield create_data_chunk(
                    {"text": "partial", "message_id": "m1"}, index=0, is_last=False
                )
                await asyncio.Event().wait()
            finally:
                closed.append(True)

        with patch("botcore_agents.task_stream.llm_chat_stream", chat):
            stream = orchestrator.assign_task_stream("Long task", agent="researcher")
            async for chunk in stream:
                if chunk.type == "data":
                    break
            await stream.aclose()

        assert closed == [True]

    async def test_chat_stream_without_a_result_fails_the_task(self, orchestrator, mock_llm):
        await _started(orchestrator)

        async def chat(session_id, message, attachments=None, timeout=None):
            yield create_data_chunk({"text": "cut off", "message_id": "m1"}, index=0, is_last=True)

        with patch("botcore_agents.task_stream.llm_chat_stream", chat):
            chunks = await _collect(orchestrator.assign_task_stream("Task", agent="researcher"))

        assert chunks[-1].type == "error"
        assert chunks[-1].error.code == "TASK_EXECUTION_ERROR"
        assert "without a result" in chunks[-1].error.message
        assert chunks[-1].chunks_before_error == 1


class TestResumeTaskStream:
    async def test_resumes_a_pending_task(self, orchestrator, mock_llm):
        await _started(orchestrator)
        task = Task(description="Resume work", status="pending")
        orchestrator._tasks[task.id] = task

        with _chat_stream("done"):
            chunks = await _collect(orchestrator.resume_task_stream(task.id, agent="researcher"))

        assert chunks[-1].type == "complete"
        assert chunks[-1].data["task_id"] == task.id
        assert {c.data["task_id"] for c in chunks if c.type == "data"} == {task.id}
        assert orchestrator.tasks[task.id].status == "completed"

    async def test_rejects_a_finished_task(self, orchestrator, mock_llm):
        task = Task(description="Already done", status="completed")
        orchestrator._tasks[task.id] = task

        chunks = await _collect(orchestrator.resume_task_stream(task.id, agent="researcher"))

        assert [c.type for c in chunks] == ["error"]
        assert chunks[0].error.code == "TASK_NOT_RESUMABLE"


class TestCollectors:
    async def test_assign_task_returns_the_streamed_result(self, orchestrator, mock_llm):
        await _started(orchestrator)
        with _chat_stream("All ", "good"):
            result = await orchestrator.assign_task("Check", agent="researcher")

        data = assert_success(result)
        assert data["result"] == "All good"
        assert data["status"] == "completed"

    async def test_task_assign_stream_command(self, orchestrator, mock_llm):
        await _started(orchestrator)
        with patch.object(commands_mod, "_get_orch", return_value=orchestrator):
            chunks = await _collect(commands_mod.task_assign_stream("Work", agent="researcher"))
            result = await commands_mod.task_resume("missing")

        assert chunks[-1].type == "complete"
        assert_error(result, "TASK_NOT_FOUND")
