"""Tests for botcore.commands.skill.frontmatter — YAML frontmatter parse/write."""

from __future__ import annotations

from pathlib import Path

from botcore.commands.skill.frontmatter import (
    SkillManifest,
    parse_frontmatter,
    read_skill_manifest,
    render_frontmatter,
    update_skill_source,
)

# ── parse_frontmatter ──────────────────────────────────────────────────


def test_parse_basic_frontmatter() -> None:
    """Parse a well-formed frontmatter block."""
    content = """\
---
name: security
description: Audit code for vulnerabilities.
version: "3.0.0"
triggers:
  - security
  - vulnerability
---

# Security

Body content here.
"""
    manifest, body = parse_frontmatter(content)

    assert manifest.name == "security"
    assert manifest.description == "Audit code for vulnerabilities."
    assert manifest.version == "3.0.0"
    assert manifest.triggers == ["security", "vulnerability"]
    assert "# Security" in body


def test_parse_multiline_description() -> None:
    """Parse YAML folded scalar description."""
    content = """\
---
name: testing
description: >
  Write unit and E2E tests following best practices.
  Use when adding tests.
version: "2.1.0"
---

Body.
"""
    manifest, body = parse_frontmatter(content)

    assert manifest.name == "testing"
    assert "Write unit and E2E tests" in manifest.description
    assert "Body." in body


def test_parse_no_frontmatter() -> None:
    """Content without --- delimiters returns empty manifest and full body."""
    content = "# Just a markdown file\n\nNo frontmatter here."
    manifest, body = parse_frontmatter(content)

    assert manifest.name == ""
    assert body == content


def test_parse_invalid_yaml() -> None:
    """Invalid YAML in frontmatter returns empty manifest."""
    content = "---\n: bad: yaml: [unclosed\n---\n\nBody."
    manifest, body = parse_frontmatter(content)

    assert manifest.name == ""


def test_parse_extra_fields_preserved() -> None:
    """Unknown fields are preserved via extra='allow'."""
    content = """\
---
name: test
description: A test.
version: "1.0.0"
portable: true
custom_field: custom_value
---

Body.
"""
    manifest, body = parse_frontmatter(content)

    assert manifest.name == "test"
    assert manifest.portable is True
    assert manifest.model_extra.get("custom_field") == "custom_value"


def test_parse_empty_frontmatter() -> None:
    """Frontmatter with no fields returns defaults."""
    content = "---\n---\n\nBody."
    manifest, body = parse_frontmatter(content)

    assert manifest.name == ""
    assert manifest.version == "0.0.0"
    assert "Body." in body


def test_parse_source_field() -> None:
    """source: field is parsed correctly."""
    content = """\
---
name: security
source: botcore
description: Test.
version: "1.0.0"
---
"""
    manifest, _ = parse_frontmatter(content)

    assert manifest.source == "botcore"


# ── render_frontmatter ─────────────────────────────────────────────────


def test_render_basic() -> None:
    """Render a manifest to frontmatter string."""
    manifest = SkillManifest(
        name="testing",
        description="Run tests.",
        version="2.0.0",
        triggers=["test", "coverage"],
    )
    result = render_frontmatter(manifest, "\n# Testing\n\nBody.\n")

    assert result.startswith("---\n")
    assert "name: testing" in result
    assert ("version: '2.0.0'" in result or 'version: "2.0.0"' in result
            or "version: 2.0.0" in result)
    assert "---\n" in result
    assert "# Testing" in result


def test_render_with_source() -> None:
    """source: appears in rendered output."""
    manifest = SkillManifest(
        name="test",
        source="botcore",
        description="Test.",
        version="1.0.0",
    )
    result = render_frontmatter(manifest)

    assert "source: botcore" in result


def test_render_field_order() -> None:
    """Fields are rendered in deterministic order."""
    manifest = SkillManifest(
        name="test",
        source="botcore",
        description="A test skill.",
        version="1.0.0",
        triggers=["test"],
    )
    result = render_frontmatter(manifest)

    name_pos = result.index("name:")
    source_pos = result.index("source:")
    desc_pos = result.index("description:")
    version_pos = result.index("version:")
    triggers_pos = result.index("triggers:")

    assert name_pos < source_pos < desc_pos < version_pos < triggers_pos


def test_render_long_description_uses_folded() -> None:
    """Long descriptions use YAML folded scalar (>)."""
    manifest = SkillManifest(
        name="test",
        description="A" * 80,  # > 60 chars
        version="1.0.0",
    )
    result = render_frontmatter(manifest)

    assert "description: >" in result


def test_render_omits_empty_triggers() -> None:
    """Empty triggers list is not rendered."""
    manifest = SkillManifest(name="test", description="Test.", version="1.0.0")
    result = render_frontmatter(manifest)

    assert "triggers:" not in result


# ── read_skill_manifest ────────────────────────────────────────────────


def test_read_skill_manifest(tmp_path: Path) -> None:
    """Read manifest from a skill directory."""
    skill_dir = tmp_path / "security"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: security\ndescription: Test.\nversion: '1.0.0'\n---\n\nBody.\n",
        encoding="utf-8",
    )

    manifest = read_skill_manifest(skill_dir)

    assert manifest is not None
    assert manifest.name == "security"
    assert manifest.version == "1.0.0"


def test_read_skill_manifest_lowercase(tmp_path: Path) -> None:
    """Reads skill.md if SKILL.md doesn't exist."""
    skill_dir = tmp_path / "test"
    skill_dir.mkdir()
    (skill_dir / "skill.md").write_text(
        "---\nname: test\ndescription: A test.\n---\n\n",
        encoding="utf-8",
    )

    manifest = read_skill_manifest(skill_dir)

    assert manifest is not None
    assert manifest.name == "test"


def test_read_skill_manifest_no_file(tmp_path: Path) -> None:
    """Returns None if no SKILL.md exists."""
    skill_dir = tmp_path / "empty"
    skill_dir.mkdir()

    assert read_skill_manifest(skill_dir) is None


def test_read_skill_manifest_no_name(tmp_path: Path) -> None:
    """Returns None if SKILL.md has no name field."""
    skill_dir = tmp_path / "noname"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("---\ndescription: No name.\n---\n", encoding="utf-8")

    assert read_skill_manifest(skill_dir) is None


# ── update_skill_source ────────────────────────────────────────────────


def test_update_skill_source(tmp_path: Path) -> None:
    """Add source: to an existing skill."""
    skill_dir = tmp_path / "testing"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: testing\ndescription: Test.\nversion: '1.0.0'\n---\n\n# Testing\n",
        encoding="utf-8",
    )

    result = update_skill_source(skill_dir, "botcore")
    assert result is True

    updated = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    assert "source: botcore" in updated
    assert "# Testing" in updated


def test_update_skill_source_no_file(tmp_path: Path) -> None:
    """Returns False if no SKILL.md exists."""
    skill_dir = tmp_path / "missing"
    skill_dir.mkdir()

    assert update_skill_source(skill_dir, "botcore") is False


def test_update_skill_source_replaces_existing(tmp_path: Path) -> None:
    """Replaces existing source: field."""
    skill_dir = tmp_path / "test"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: test\nsource: old\ndescription: Test.\nversion: '1.0.0'\n---\n\nBody.\n",
        encoding="utf-8",
    )

    update_skill_source(skill_dir, "new-source")

    updated = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    assert "source: new-source" in updated
    assert "source: old" not in updated
