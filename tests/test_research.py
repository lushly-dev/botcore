"""Tests for botcore.commands.research — Gemini research commands."""

from __future__ import annotations

from unittest.mock import patch

from botcore.commands.research import research_query


async def test_research_invalid_mode() -> None:
    """research_query rejects invalid mode."""
    result = await research_query("test", mode="invalid")
    assert result.success is False
    assert result.error.code == "INVALID_MODE"


async def test_research_missing_package() -> None:
    """research_query errors when google-genai is not installed."""
    with patch("botcore.commands.research._check_genai_available", return_value=False):
        result = await research_query("test")

    assert result.success is False
    assert result.error.code == "MISSING_PACKAGE"


async def test_research_missing_api_key() -> None:
    """research_query errors when GEMINI_API_KEY is not set."""
    with (
        patch("botcore.commands.research._check_genai_available", return_value=True),
        patch.dict("os.environ", {}, clear=True),
    ):
        result = await research_query("test")

    assert result.success is False
    assert result.error.code == "MISSING_API_KEY"
