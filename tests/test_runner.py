"""Tests for botcore.utils.runner."""

from __future__ import annotations

import sys

from botcore.utils.runner import MAX_OUTPUT_LENGTH, run_command, run_python_module, smart_truncate


def test_smart_truncate_short() -> None:
    """Short output returned unchanged."""
    assert smart_truncate("hello") == "hello"


def test_smart_truncate_long() -> None:
    """Long output preserves head and tail with truncation marker."""
    text = "x" * 20_000
    result = smart_truncate(text)
    assert len(result) < len(text)
    assert "chars truncated" in result
    assert result.startswith("x" * 3000)
    assert result.endswith("x" * 4000)


async def test_run_command_success() -> None:
    """Successful command returns success=True with output."""
    result = await run_command([sys.executable, "-c", "print('hello')"])
    assert result["success"] is True
    assert "hello" in result["output"]
    assert result["error"] is None


async def test_run_command_failure() -> None:
    """Failed command returns success=False with error output."""
    result = await run_command([sys.executable, "-c", "import sys; sys.exit(1)"])
    assert result["success"] is False


async def test_run_command_bad_executable() -> None:
    """Non-existent command returns success=False with error string."""
    result = await run_command(["__nonexistent_command_xyz__"])
    assert result["success"] is False
    assert result["error"] is not None


async def test_run_command_large_output() -> None:
    """Output exceeding MAX_OUTPUT_LENGTH is truncated."""
    code = f"print('x' * {MAX_OUTPUT_LENGTH + 5000})"
    result = await run_command([sys.executable, "-c", code])
    assert result["success"] is True
    assert "chars truncated" in result["output"]


async def test_run_python_module() -> None:
    """run_python_module delegates to run_command correctly."""
    result = await run_python_module("platform")
    assert result["success"] is True
    assert result["output"]  # platform module prints platform info
