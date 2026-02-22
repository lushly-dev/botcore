"""Tests for botcore.commands.info."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

from botcore.commands.info import info_env, info_scripts, info_workspace


async def test_info_workspace_found(tmp_workspace: Path) -> None:
    """Returns workspace path and packages."""
    with patch("botcore.commands.info.find_workspace", return_value=tmp_workspace):
        result = await info_workspace()

    assert result.success is True
    assert result.data["workspace_root"] == str(tmp_workspace)
    assert isinstance(result.data["packages"], list)


async def test_info_workspace_not_found() -> None:
    """Returns error CommandResult when no workspace."""
    with patch("botcore.commands.info.find_workspace", return_value=None):
        result = await info_workspace()

    assert result.success is False
    assert result.error is not None
    assert "WORKSPACE_NOT_FOUND" in str(result.error)


async def test_info_env() -> None:
    """Returns python version and platform."""
    result = await info_env()

    assert result.success is True
    assert sys.version in result.data["python_version"]
    assert result.data["platform"] == sys.platform
    assert result.data["cwd"] == os.getcwd()


async def test_info_scripts(tmp_workspace_with_packages: Path) -> None:
    """Reads package.json scripts correctly."""
    # Add scripts to one of the packages
    pkg_core = tmp_workspace_with_packages / "packages" / "core"
    (pkg_core / "package.json").write_text(
        '{"name": "@test/core", "scripts": {"build": "tsc", "test": "vitest"}}',
        encoding="utf-8",
    )

    with patch("botcore.commands.info.find_workspace", return_value=tmp_workspace_with_packages):
        result = await info_scripts()

    assert result.success is True
    assert "core" in result.data
    assert "build" in result.data["core"]
    assert "test" in result.data["core"]


async def test_info_scripts_no_workspace() -> None:
    """Returns error when no workspace found."""
    with patch("botcore.commands.info.find_workspace", return_value=None):
        result = await info_scripts()

    assert result.success is False


async def test_info_workspace_with_packages(tmp_workspace_with_packages: Path) -> None:
    """Workspace with packages reports correct count."""
    with patch("botcore.commands.info.find_workspace", return_value=tmp_workspace_with_packages):
        result = await info_workspace()

    assert result.success is True
    assert result.data["package_count"] == 3
    assert "core" in result.data["packages"]
    assert "data" in result.data["packages"]
    assert "utils" in result.data["packages"]
