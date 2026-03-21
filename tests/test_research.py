"""Tests for botcore.commands.research — Gemini research commands."""

from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from afd.testing import (
    assert_error,
    assert_has_confidence,
    assert_has_reasoning,
    assert_has_sources,
    assert_success,
)

from botcore.commands.research import research_query


async def test_research_invalid_mode() -> None:
    """research_query rejects invalid mode."""
    result = await research_query("test", mode="invalid")
    assert_error(result, "INVALID_MODE")


async def test_research_missing_package() -> None:
    """research_query errors when google-genai is not installed."""
    with patch("botcore.commands.research._check_genai_available", return_value=False):
        result = await research_query("test")

    assert_error(result, "MISSING_PACKAGE")


async def test_research_missing_api_key() -> None:
    """research_query errors when GEMINI_API_KEY is not set."""
    with (
        patch("botcore.commands.research._check_genai_available", return_value=True),
        patch.dict("os.environ", {}, clear=True),
    ):
        result = await research_query("test")

    assert_error(result, "MISSING_API_KEY")


async def test_research_success_includes_afd_metadata() -> None:
    """research_query returns confidence, sources, and reasoning on success."""
    response = SimpleNamespace(
        text="Grounded answer",
        candidates=[
            SimpleNamespace(
                grounding_metadata=SimpleNamespace(
                    grounding_chunks=[
                        SimpleNamespace(web=SimpleNamespace(uri="https://example.com/a")),
                        SimpleNamespace(web=SimpleNamespace(uri="https://example.com/b")),
                    ],
                ),
            ),
        ],
    )

    fake_client = SimpleNamespace(
        models=SimpleNamespace(generate_content=lambda **kwargs: response),
    )
    fake_genai = ModuleType("google.genai")
    fake_genai.Client = lambda api_key: fake_client

    fake_types = ModuleType("google.genai.types")
    fake_types.GenerateContentConfig = lambda **kwargs: SimpleNamespace(**kwargs)
    fake_types.GoogleSearch = lambda: SimpleNamespace()
    fake_types.Tool = lambda **kwargs: SimpleNamespace(**kwargs)

    fake_google = ModuleType("google")
    fake_google.genai = fake_genai

    with (
        patch("botcore.commands.research._check_genai_available", return_value=True),
        patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}, clear=True),
        patch.dict(sys.modules, {
            "google": fake_google,
            "google.genai": fake_genai,
            "google.genai.types": fake_types,
        }),
    ):
        result = await research_query("test query")

    data = assert_success(result)
    assert data["answer"] == "Grounded answer"
    assert data["sources"] == ["https://example.com/a", "https://example.com/b"]
    assert_has_confidence(result, min_confidence=0.8, max_confidence=0.9)
    assert_has_reasoning(result, contains="Research completed via")
    sources = assert_has_sources(result, min_count=2)
    assert [source.url for source in sources] == ["https://example.com/a", "https://example.com/b"]
