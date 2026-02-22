"""Botcore research commands — web research via Gemini + Google Search."""

from __future__ import annotations

import os
from typing import Any

from afd import CommandResult, error, success

# Gemini 3 series models
SEARCH_MODELS = {
    "fast": "gemini-3-flash-preview",
    "deep": "gemini-3-pro-preview",
    "thinking": "gemini-3-pro-preview",
}


def _check_genai_available() -> bool:
    """Check if google-genai is installed."""
    try:
        from google import genai  # noqa: F401

        return True
    except ImportError:
        return False


def _extract_sources(response: Any) -> list[str]:
    """Extract sources from grounding metadata."""
    sources: list[str] = []
    if hasattr(response, "candidates") and response.candidates:
        candidate = response.candidates[0]
        if hasattr(candidate, "grounding_metadata"):
            metadata = candidate.grounding_metadata
            if metadata and hasattr(metadata, "grounding_chunks") and metadata.grounding_chunks:
                for chunk in metadata.grounding_chunks:
                    if hasattr(chunk, "web") and hasattr(chunk.web, "uri"):
                        sources.append(chunk.web.uri)
    return sources[:10]


async def research_query(query: str, mode: str = "fast") -> CommandResult[dict]:
    """Run a research query with Gemini and Google Search.

    Args:
        query: The research query
        mode: 'fast' (default) or 'deep' for more thorough research

    Requires google-genai: pip install botcore[research]
    """
    if mode not in ["fast", "deep", "thinking"]:
        return error(
            "INVALID_MODE",
            f"Invalid mode: {mode}",
            suggestion="Use mode='fast' (default) or mode='deep'",
        )

    if not _check_genai_available():
        return error(
            "MISSING_PACKAGE",
            "google-genai package not installed",
            suggestion="Install with: pip install botcore[research]",
        )

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return error(
            "MISSING_API_KEY",
            "GEMINI_API_KEY environment variable not set",
            suggestion="Set GEMINI_API_KEY in environment or .env file",
        )

    from google import genai
    from google.genai.types import GenerateContentConfig, GoogleSearch, Tool

    model_name = SEARCH_MODELS.get(mode, SEARCH_MODELS["fast"])

    try:
        client = genai.Client(api_key=api_key)

        config = GenerateContentConfig(
            tools=[Tool(google_search=GoogleSearch())],
            temperature=0.7 if mode == "fast" else 0.5,
        )

        response = client.models.generate_content(
            model=model_name,
            contents=query,
            config=config,
        )

        result_text = response.text
        sources = _extract_sources(response)

        MAX_RESEARCH_LENGTH = 12000
        if len(result_text) > MAX_RESEARCH_LENGTH:
            result_text = result_text[:MAX_RESEARCH_LENGTH] + "\n\n... (truncated for token safety)"

        return success(
            data={
                "answer": result_text,
                "query": query,
                "mode": mode,
                "model": model_name,
                "sources": sources,
            },
            reasoning=f"Research completed via {model_name}",
        )

    except Exception as e:
        return error(
            "RESEARCH_FAILED",
            f"Research query failed: {e}",
            suggestion="Check API key and network connectivity",
        )
