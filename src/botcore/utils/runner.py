"""Command runner utilities for botcore."""

from __future__ import annotations

import asyncio
import shutil
import sys
import warnings
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, TypeVar

_T = TypeVar("_T")

MAX_OUTPUT_LENGTH = 8000


def smart_truncate(output: str, max_len: int = MAX_OUTPUT_LENGTH) -> str:
    """Truncate output while preserving head and tail."""
    if len(output) <= max_len:
        return output

    head = output[:3000]
    tail = output[-4000:]
    omitted = len(output) - 7000

    return f"{head}\n\n... [{omitted:,} chars truncated] ...\n\n{tail}"


async def run_command(
    command: list[str],
    cwd: Path | None = None,
    timeout: int = 300,
) -> dict[str, Any]:
    """Run a command asynchronously and return result.

    Args:
        command: Command and arguments as list.
        cwd: Working directory (optional).
        timeout: Timeout in seconds (default 300).

    Returns:
        Dict with success, output, and error keys.
    """
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )

        try:
            stdout_data, stderr_data = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
        except TimeoutError:
            process.kill()
            return {"success": False, "error": f"Command timed out after {timeout}s"}

        output = stdout_data.decode("utf-8", errors="replace")
        error_output = stderr_data.decode("utf-8", errors="replace")

        if len(output) > MAX_OUTPUT_LENGTH:
            output = smart_truncate(output, MAX_OUTPUT_LENGTH)

        if len(error_output) > MAX_OUTPUT_LENGTH:
            error_output = smart_truncate(error_output, MAX_OUTPUT_LENGTH)

        return {
            "success": process.returncode == 0,
            "output": output,
            "error": error_output if process.returncode != 0 else None,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def run_external_tool(
    tool: str,
    args: list[str],
    install_hint: str,
    cwd: Path | None = None,
) -> dict[str, Any] | None:
    """Run an external tool, returning None with a warning if not installed.

    Args:
        tool: Executable name (e.g., "npx", "cargo").
        args: Arguments to pass after the tool name.
        install_hint: Installation command shown in the warning.
        cwd: Working directory.

    Returns:
        Result dict from run_command, or None if tool not found.
    """
    if not shutil.which(tool):
        warnings.warn(
            f"{tool} not found. Install with: {install_hint}",
            UserWarning,
            stacklevel=2,
        )
        return None
    return await run_command([tool, *args], cwd=cwd)


async def run_python_module(
    module: str,
    args: list[str] | None = None,
    cwd: Path | None = None,
) -> dict[str, Any]:
    """Run a Python module (python -m module args).

    Args:
        module: Module name (e.g., "ruff", "pytest").
        args: Additional arguments.
        cwd: Working directory.

    Returns:
        Dict with success, output, and error keys.
    """
    command = [sys.executable, "-m", module]
    if args:
        command.extend(args)
    return await run_command(command, cwd=cwd)


async def retry_async(
    fn: Callable[[], Awaitable[_T]],
    attempts: int = 10,
    delay_s: float = 0.3,
) -> _T:
    """Retry an async callable until it succeeds or attempts are exhausted.

    Args:
        fn: Zero-argument async callable to retry.
        attempts: Maximum number of attempts.
        delay_s: Delay between attempts in seconds.

    Returns:
        The return value of *fn* on success.

    Raises:
        The last exception raised by *fn* if all attempts fail.
    """
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            return await fn()
        except Exception as exc:
            last_exc = exc
            if attempt < attempts - 1:
                await asyncio.sleep(delay_s)
    if last_exc:
        raise last_exc
    raise RuntimeError("retry_async: all attempts failed")
