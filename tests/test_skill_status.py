"""Tests for botcore.commands.skill.status — version drift detection."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from afd.testing import assert_error, assert_success

from botcore.commands.skill.status import skill_status


def _make_skill(base: Path, name: str, version: str = "1.0.0", source: str | None = None) -> Path:
    """Create a minimal skill directory."""
    skill_dir = base / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    source_line = f"\nsource: {source}" if source else ""
    content = (
        f"---\nname: {name}\ndescription: A {name} skill."
        f"{source_line}\nversion: '{version}'\n---\n\nBody.\n"
    )
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
    return skill_dir


def _setup_workspace(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'test'\nversion = '0.1.0'\n\n[tool.botcore]\n",
        encoding="utf-8",
    )
    return tmp_path


async def test_status_no_workspace() -> None:
    """Returns error when no workspace found."""
    with patch("botcore.commands.skill.status.find_workspace", return_value=None):
        result = await skill_status()

    assert_error(result, "NO_WORKSPACE")


async def test_status_ok(tmp_path: Path) -> None:
    """Skill at same version and source shows 'ok'."""
    ws = _setup_workspace(tmp_path)
    skills_dir = ws / ".claude" / "skills"
    skills_dir.mkdir(parents=True)
    _make_skill(skills_dir, "security", "3.0.0", source="botcore")

    source = tmp_path / "source"
    source.mkdir()
    _make_skill(source, "security", "3.0.0")

    from botcore.commands.skill._discovery import DiscoveredSkill
    from botcore.commands.skill.frontmatter import read_skill_manifest

    m = read_skill_manifest(source / "security")
    available = {
        "security": DiscoveredSkill(
            name="security", source="botcore", source_path=source / "security", manifest=m
        )
    }

    with (
        patch("botcore.commands.skill.status.find_workspace", return_value=ws),
        patch("botcore.commands.skill.status.discover_available_skills", return_value=available),
    ):
        result = await skill_status()

    data = assert_success(result)
    sec = next(s for s in data["skills"] if s["name"] == "security")
    assert sec["status"] == "ok"
    assert data["summary"]["ok"] == 1


async def test_status_stale(tmp_path: Path) -> None:
    """Skill with older local version shows 'stale'."""
    ws = _setup_workspace(tmp_path)
    skills_dir = ws / ".claude" / "skills"
    skills_dir.mkdir(parents=True)
    _make_skill(skills_dir, "security", "1.0.0", source="botcore")

    source = tmp_path / "source"
    source.mkdir()
    _make_skill(source, "security", "3.0.0")

    from botcore.commands.skill._discovery import DiscoveredSkill
    from botcore.commands.skill.frontmatter import read_skill_manifest

    m = read_skill_manifest(source / "security")
    available = {
        "security": DiscoveredSkill(
            name="security", source="botcore", source_path=source / "security", manifest=m
        )
    }

    with (
        patch("botcore.commands.skill.status.find_workspace", return_value=ws),
        patch("botcore.commands.skill.status.discover_available_skills", return_value=available),
    ):
        result = await skill_status()

    data = assert_success(result)
    sec = next(s for s in data["skills"] if s["name"] == "security")
    assert sec["status"] == "stale"


async def test_status_missing(tmp_path: Path) -> None:
    """Available skill not installed locally shows 'missing'."""
    ws = _setup_workspace(tmp_path)

    from botcore.commands.skill._discovery import DiscoveredSkill
    from botcore.commands.skill.frontmatter import SkillManifest

    available = {
        "testing": DiscoveredSkill(
            name="testing",
            source="botcore",
            source_path=tmp_path / "src" / "testing",
            manifest=SkillManifest(name="testing", version="2.0.0"),
        )
    }

    with (
        patch("botcore.commands.skill.status.find_workspace", return_value=ws),
        patch("botcore.commands.skill.status.discover_available_skills", return_value=available),
    ):
        result = await skill_status()

    data = assert_success(result)
    test = next(s for s in data["skills"] if s["name"] == "testing")
    assert test["status"] == "missing"


async def test_status_unmanaged(tmp_path: Path) -> None:
    """Local skill without source: field shows 'unmanaged'."""
    ws = _setup_workspace(tmp_path)
    skills_dir = ws / ".claude" / "skills"
    skills_dir.mkdir(parents=True)
    _make_skill(skills_dir, "security", "1.0.0")  # no source

    from botcore.commands.skill._discovery import DiscoveredSkill
    from botcore.commands.skill.frontmatter import read_skill_manifest

    source = tmp_path / "source"
    source.mkdir()
    _make_skill(source, "security", "3.0.0")
    m = read_skill_manifest(source / "security")
    available = {
        "security": DiscoveredSkill(
            name="security", source="botcore", source_path=source / "security", manifest=m
        )
    }

    with (
        patch("botcore.commands.skill.status.find_workspace", return_value=ws),
        patch("botcore.commands.skill.status.discover_available_skills", return_value=available),
    ):
        result = await skill_status()

    data = assert_success(result)
    sec = next(s for s in data["skills"] if s["name"] == "security")
    assert sec["status"] == "unmanaged"


async def test_status_conflict(tmp_path: Path) -> None:
    """Local skill with different source shows 'conflict'."""
    ws = _setup_workspace(tmp_path)
    skills_dir = ws / ".claude" / "skills"
    skills_dir.mkdir(parents=True)
    _make_skill(skills_dir, "security", "1.0.0", source="other-plugin")

    from botcore.commands.skill._discovery import DiscoveredSkill
    from botcore.commands.skill.frontmatter import read_skill_manifest

    source = tmp_path / "source"
    source.mkdir()
    _make_skill(source, "security", "3.0.0")
    m = read_skill_manifest(source / "security")
    available = {
        "security": DiscoveredSkill(
            name="security", source="botcore", source_path=source / "security", manifest=m
        )
    }

    with (
        patch("botcore.commands.skill.status.find_workspace", return_value=ws),
        patch("botcore.commands.skill.status.discover_available_skills", return_value=available),
    ):
        result = await skill_status()

    data = assert_success(result)
    sec = next(s for s in data["skills"] if s["name"] == "security")
    assert sec["status"] == "conflict"
