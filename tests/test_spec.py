"""Tests for botcore.commands.spec — specification lifecycle."""

from __future__ import annotations

from botcore.commands.spec import spec_create, spec_status, spec_validate


async def test_spec_create_proposal(tmp_path) -> None:
    """spec_create writes a proposal with frontmatter."""
    path = str(tmp_path / "my-feature.md")
    result = await spec_create(path, template="proposal")

    assert result.success is True
    assert result.data["template"] == "proposal"
    assert "My Feature" in result.data["title"]

    content = (tmp_path / "my-feature.md").read_text()
    assert "status: Draft" in content
    assert "## Problem Statement" in content


async def test_spec_create_spec_template(tmp_path) -> None:
    """spec_create writes a spec with proposal reference."""
    path = str(tmp_path / "api-design.md")
    result = await spec_create(path, template="spec")

    assert result.success is True
    content = (tmp_path / "api-design.md").read_text()
    assert "## Implementation Plan" in content


async def test_spec_create_file_exists(tmp_path) -> None:
    """spec_create errors when file already exists."""
    existing = tmp_path / "existing.md"
    existing.write_text("already here")

    result = await spec_create(str(existing))
    assert result.success is False
    assert result.error.code == "FILE_EXISTS"


async def test_spec_create_invalid_template() -> None:
    """spec_create errors on unknown template."""
    result = await spec_create("test.md", template="unknown")
    assert result.success is False
    assert result.error.code == "INVALID_TEMPLATE"


async def test_spec_status(tmp_path) -> None:
    """spec_status reads status from frontmatter."""
    spec = tmp_path / "feature.md"
    spec.write_text("---\ntitle: Feature\nstatus: Approved\n---\n# Feature\n")

    result = await spec_status(str(spec))
    assert result.success is True
    assert result.data["status"] == "Approved"


async def test_spec_status_not_found() -> None:
    """spec_status errors for missing file."""
    result = await spec_status("/nonexistent/path.md")
    assert result.success is False
    assert result.error.code == "FILE_NOT_FOUND"


async def test_spec_validate_valid(tmp_path) -> None:
    """spec_validate passes for well-formed spec."""
    spec = tmp_path / "good.md"
    spec.write_text(
        "---\ntitle: Good Spec\nstatus: Draft\n---\n\n"
        "# Good Spec\n\n## Overview\n\nThis is a well-formed spec with enough content "
        "to pass the length check. " * 10
    )

    result = await spec_validate(str(spec))
    assert result.success is True
    assert result.data["valid"] is True


async def test_spec_validate_issues(tmp_path) -> None:
    """spec_validate catches structural issues."""
    spec = tmp_path / "bad.md"
    spec.write_text("Too short")

    result = await spec_validate(str(spec))
    assert result.success is True
    assert result.data["valid"] is False
    assert len(result.data["issues"]) > 0
