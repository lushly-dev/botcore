"""Tests for botcore.commands.docs — documentation commands."""

from __future__ import annotations

from unittest.mock import patch

from botcore.commands.docs import (
    _extract_headings,
    _slugify_heading,
    docs_check_changelog,
    docs_lint,
)


def test_slugify_heading() -> None:
    """Heading slugification works correctly."""
    assert _slugify_heading("Hello World") == "hello-world"
    assert _slugify_heading("API Changes (v2)") == "api-changes-v2"
    assert _slugify_heading("## Nested!") == "nested"


def test_extract_headings() -> None:
    """Heading extraction finds all levels."""
    content = "# Title\n\nSome text.\n\n## Section One\n\n### Sub Section\n"
    headings = _extract_headings(content)
    assert "title" in headings
    assert "section-one" in headings
    assert "sub-section" in headings


async def test_docs_lint_no_docs_dir(tmp_path) -> None:
    """docs_lint errors when docs directory doesn't exist."""
    with patch("botcore.commands.docs.find_workspace", return_value=tmp_path):
        result = await docs_lint()

    assert result.success is False
    assert result.error.code == "PATH_NOT_FOUND"


async def test_docs_lint_no_issues(tmp_path) -> None:
    """docs_lint passes with valid markdown."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "readme.md").write_text("# Hello\n\nSome content.\n")

    with patch("botcore.commands.docs.find_workspace", return_value=tmp_path):
        result = await docs_lint()

    assert result.success is True
    assert result.data["files_checked"] == 1
    assert result.data["passed"] is True


async def test_docs_lint_broken_link(tmp_path) -> None:
    """docs_lint catches broken internal links."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "page.md").write_text("# Page\n\nSee [other](./nonexistent.md).\n")

    with patch("botcore.commands.docs.find_workspace", return_value=tmp_path):
        result = await docs_lint()

    assert result.success is False
    assert result.error.code == "BROKEN_LINKS"


async def test_docs_check_changelog_no_workspace() -> None:
    """docs_check_changelog errors without workspace."""
    with patch("botcore.commands.docs.find_workspace", return_value=None):
        result = await docs_check_changelog()

    assert result.success is False
    assert result.error.code == "NO_WORKSPACE"


async def test_docs_check_changelog_no_file(tmp_path) -> None:
    """docs_check_changelog succeeds when no CHANGELOG.md exists."""
    with patch("botcore.commands.docs.find_workspace", return_value=tmp_path):
        result = await docs_check_changelog()

    assert result.success is True
    assert result.data["has_changelog"] is False
