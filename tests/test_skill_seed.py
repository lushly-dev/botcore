"""Tests for botcore.commands.skill.seed — skill seeding."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from botcore.commands.skill.seed import skill_seed


def _make_source_skill(
    base: Path, name: str, version: str = "1.0.0", source: str | None = None
) -> Path:
    """Create a source skill directory."""
    skill_dir = base / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    source_line = f"\nsource: {source}" if source else ""
    content = (
        f"---\nname: {name}\ndescription: A {name} skill."
        f"{source_line}\nversion: '{version}'\n---\n\nBody.\n"
    )
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
    return skill_dir


def _make_source_skill_with_refs(
    base: Path, name: str, version: str = "1.0.0"
) -> Path:
    """Create a source skill with references/ dir."""
    skill_dir = _make_source_skill(base, name, version)
    refs = skill_dir / "references"
    refs.mkdir()
    (refs / "guide.md").write_text("# Guide\n\nContent.", encoding="utf-8")
    return skill_dir


def _setup_workspace(tmp_path: Path) -> Path:
    """Create workspace with pyproject.toml."""
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'test'\nversion = '0.1.0'\n\n[tool.botcore]\n",
        encoding="utf-8",
    )
    return tmp_path


async def test_seed_no_workspace() -> None:
    """Returns error when no workspace found."""
    with patch("botcore.commands.skill.seed.find_workspace", return_value=None):
        result = await skill_seed()

    assert result.success is False
    assert result.error.code == "NO_WORKSPACE"


async def test_seed_no_available_skills(tmp_path: Path) -> None:
    """Returns error when no skills are available."""
    ws = _setup_workspace(tmp_path)
    bundled = tmp_path / "empty_bundled"
    bundled.mkdir()

    with (
        patch("botcore.commands.skill.seed.find_workspace", return_value=ws),
        patch(
            "botcore.commands.skill.seed.discover_available_skills",
            return_value={},
        ),
    ):
        result = await skill_seed()

    assert result.success is False
    assert result.error.code == "NO_SKILLS_AVAILABLE"


async def test_seed_creates_new_skills(tmp_path: Path) -> None:
    """Seeds skills into empty project."""
    ws = _setup_workspace(tmp_path)
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    _make_source_skill(source_dir, "security", "3.0.0")
    _make_source_skill(source_dir, "testing", "2.0.0")

    from botcore.commands.skill._discovery import DiscoveredSkill
    from botcore.commands.skill.frontmatter import read_skill_manifest

    available = {}
    for name in ["security", "testing"]:
        m = read_skill_manifest(source_dir / name)
        available[name] = DiscoveredSkill(
            name=name, source="botcore", source_path=source_dir / name, manifest=m
        )

    with (
        patch("botcore.commands.skill.seed.find_workspace", return_value=ws),
        patch("botcore.commands.skill.seed.discover_available_skills", return_value=available),
    ):
        result = await skill_seed()

    assert result.success is True
    assert sorted(result.data["seeded"]) == ["security", "testing"]
    assert len(result.data["skipped"]) == 0

    # Verify files were copied and source: injected
    security_skill = ws / ".claude" / "skills" / "security" / "SKILL.md"
    assert security_skill.exists()
    content = security_skill.read_text(encoding="utf-8")
    assert "source: botcore" in content


async def test_seed_skips_different_source(tmp_path: Path) -> None:
    """Does not overwrite skills owned by a different source."""
    ws = _setup_workspace(tmp_path)
    skills_dir = ws / ".claude" / "skills"
    skills_dir.mkdir(parents=True)
    # Local skill owned by "custom-plugin"
    _make_source_skill(skills_dir, "security", "1.0.0", source="custom-plugin")

    source_dir = tmp_path / "source"
    source_dir.mkdir()
    _make_source_skill(source_dir, "security", "5.0.0")

    from botcore.commands.skill._discovery import DiscoveredSkill
    from botcore.commands.skill.frontmatter import read_skill_manifest

    m = read_skill_manifest(source_dir / "security")
    available = {
        "security": DiscoveredSkill(
            name="security", source="botcore", source_path=source_dir / "security", manifest=m
        )
    }

    with (
        patch("botcore.commands.skill.seed.find_workspace", return_value=ws),
        patch("botcore.commands.skill.seed.discover_available_skills", return_value=available),
    ):
        result = await skill_seed()

    assert result.success is True
    assert result.data["seeded"] == []
    assert len(result.data["skipped"]) == 1
    assert result.data["skipped"][0]["reason"] == "owned by custom-plugin"


async def test_seed_updates_matching_source(tmp_path: Path) -> None:
    """Updates skills with matching source when update=True."""
    ws = _setup_workspace(tmp_path)
    skills_dir = ws / ".claude" / "skills"
    skills_dir.mkdir(parents=True)
    _make_source_skill(skills_dir, "security", "1.0.0", source="botcore")

    source_dir = tmp_path / "source"
    source_dir.mkdir()
    _make_source_skill(source_dir, "security", "5.0.0")

    from botcore.commands.skill._discovery import DiscoveredSkill
    from botcore.commands.skill.frontmatter import read_skill_manifest

    m = read_skill_manifest(source_dir / "security")
    available = {
        "security": DiscoveredSkill(
            name="security", source="botcore", source_path=source_dir / "security", manifest=m
        )
    }

    with (
        patch("botcore.commands.skill.seed.find_workspace", return_value=ws),
        patch("botcore.commands.skill.seed.discover_available_skills", return_value=available),
    ):
        result = await skill_seed(update=True)

    assert result.success is True
    assert result.data["updated"] == ["security"]


async def test_seed_skips_unmanaged(tmp_path: Path) -> None:
    """Does not overwrite unmanaged skills (no source:)."""
    ws = _setup_workspace(tmp_path)
    skills_dir = ws / ".claude" / "skills"
    skills_dir.mkdir(parents=True)
    # Local skill without source:
    _make_source_skill(skills_dir, "security", "1.0.0")

    source_dir = tmp_path / "source"
    source_dir.mkdir()
    _make_source_skill(source_dir, "security", "5.0.0")

    from botcore.commands.skill._discovery import DiscoveredSkill
    from botcore.commands.skill.frontmatter import read_skill_manifest

    m = read_skill_manifest(source_dir / "security")
    available = {
        "security": DiscoveredSkill(
            name="security", source="botcore", source_path=source_dir / "security", manifest=m
        )
    }

    with (
        patch("botcore.commands.skill.seed.find_workspace", return_value=ws),
        patch("botcore.commands.skill.seed.discover_available_skills", return_value=available),
    ):
        result = await skill_seed()

    assert result.success is True
    assert result.data["seeded"] == []
    assert any("unmanaged" in s["reason"] for s in result.data["skipped"])


async def test_seed_dry_run(tmp_path: Path) -> None:
    """Dry run reports what would be seeded without writing."""
    ws = _setup_workspace(tmp_path)
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    _make_source_skill(source_dir, "testing", "1.0.0")

    from botcore.commands.skill._discovery import DiscoveredSkill
    from botcore.commands.skill.frontmatter import read_skill_manifest

    m = read_skill_manifest(source_dir / "testing")
    available = {
        "testing": DiscoveredSkill(
            name="testing", source="botcore", source_path=source_dir / "testing", manifest=m
        )
    }

    with (
        patch("botcore.commands.skill.seed.find_workspace", return_value=ws),
        patch("botcore.commands.skill.seed.discover_available_skills", return_value=available),
    ):
        result = await skill_seed(dry_run=True)

    assert result.success is True
    assert result.data["dry_run"] is True
    assert result.data["seeded"] == ["testing"]
    # File should NOT exist
    assert not (ws / ".claude" / "skills" / "testing").exists()


async def test_seed_include_filter(tmp_path: Path) -> None:
    """include: config filters to only listed skills."""
    ws = _setup_workspace(tmp_path)
    # Override config with include
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'test'\nversion = '0.1.0'"
        "\n\n[tool.botcore.skills]\ninclude = ['testing']\n",
        encoding="utf-8",
    )

    source_dir = tmp_path / "source"
    source_dir.mkdir()
    _make_source_skill(source_dir, "security", "1.0.0")
    _make_source_skill(source_dir, "testing", "1.0.0")

    from botcore.commands.skill._discovery import DiscoveredSkill
    from botcore.commands.skill.frontmatter import read_skill_manifest

    available = {}
    for name in ["security", "testing"]:
        m = read_skill_manifest(source_dir / name)
        available[name] = DiscoveredSkill(
            name=name, source="botcore", source_path=source_dir / name, manifest=m
        )

    with (
        patch("botcore.commands.skill.seed.find_workspace", return_value=ws),
        patch("botcore.commands.skill.seed.discover_available_skills", return_value=available),
    ):
        result = await skill_seed()

    assert result.success is True
    assert result.data["seeded"] == ["testing"]


async def test_seed_skip_filter(tmp_path: Path) -> None:
    """skip: config excludes listed skills."""
    ws = _setup_workspace(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'test'\nversion = '0.1.0'"
        "\n\n[tool.botcore.skills]\nskip = ['security']\n",
        encoding="utf-8",
    )

    source_dir = tmp_path / "source"
    source_dir.mkdir()
    _make_source_skill(source_dir, "security", "1.0.0")
    _make_source_skill(source_dir, "testing", "1.0.0")

    from botcore.commands.skill._discovery import DiscoveredSkill
    from botcore.commands.skill.frontmatter import read_skill_manifest

    available = {}
    for name in ["security", "testing"]:
        m = read_skill_manifest(source_dir / name)
        available[name] = DiscoveredSkill(
            name=name, source="botcore", source_path=source_dir / name, manifest=m
        )

    with (
        patch("botcore.commands.skill.seed.find_workspace", return_value=ws),
        patch("botcore.commands.skill.seed.discover_available_skills", return_value=available),
    ):
        result = await skill_seed()

    assert result.success is True
    assert result.data["seeded"] == ["testing"]


async def test_seed_copies_references(tmp_path: Path) -> None:
    """Seed copies the references/ directory along with SKILL.md."""
    ws = _setup_workspace(tmp_path)
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    _make_source_skill_with_refs(source_dir, "testing", "1.0.0")

    from botcore.commands.skill._discovery import DiscoveredSkill
    from botcore.commands.skill.frontmatter import read_skill_manifest

    m = read_skill_manifest(source_dir / "testing")
    available = {
        "testing": DiscoveredSkill(
            name="testing", source="botcore", source_path=source_dir / "testing", manifest=m
        )
    }

    with (
        patch("botcore.commands.skill.seed.find_workspace", return_value=ws),
        patch("botcore.commands.skill.seed.discover_available_skills", return_value=available),
    ):
        result = await skill_seed()

    assert result.success is True
    refs = ws / ".claude" / "skills" / "testing" / "references" / "guide.md"
    assert refs.exists()
