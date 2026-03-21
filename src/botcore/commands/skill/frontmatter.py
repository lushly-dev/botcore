"""YAML frontmatter parse/write and SkillManifest model."""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

# Deterministic field order for rendering
_FIELD_ORDER = ["name", "source", "description", "version", "triggers"]


class SkillManifest(BaseModel):
    """Skill metadata parsed from YAML frontmatter."""

    model_config = ConfigDict(extra="allow")

    name: str = ""
    description: str = ""
    version: str = "0.0.0"
    source: str | None = None
    triggers: list[str] = []
    portable: bool = False
    category: str | None = None


def parse_frontmatter(content: str) -> tuple[SkillManifest, str]:
    """Split content at --- delimiters, YAML-parse the frontmatter.

    Returns:
        (manifest, body) where body is everything after the closing ---.
    """
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)", content, re.DOTALL)
    if not match:
        return SkillManifest(), content

    yaml_str = match.group(1)
    body = match.group(2)

    try:
        data = yaml.safe_load(yaml_str)
    except yaml.YAMLError:
        return SkillManifest(), content

    if not isinstance(data, dict):
        return SkillManifest(), content

    return SkillManifest(**data), body


def render_frontmatter(manifest: SkillManifest, body: str = "") -> str:
    """Render a SkillManifest as YAML frontmatter + body.

    Fields are written in deterministic order: name, source, description,
    version, triggers, then remaining fields alphabetically.
    """
    data = manifest.model_dump(exclude_none=True, exclude_defaults=False)
    # Remove fields that are default/empty and not in the ordered set
    if not data.get("portable"):
        data.pop("portable", None)
    if not data.get("category"):
        data.pop("category", None)
    if not data.get("triggers"):
        data.pop("triggers", None)

    lines = ["---"]
    # Ordered fields first
    for key in _FIELD_ORDER:
        if key not in data:
            continue
        val = data.pop(key)
        if key == "triggers" and isinstance(val, list):
            lines.append("triggers:")
            for t in val:
                lines.append(f"  - {t}")
        elif key == "description" and len(str(val)) > 60:
            lines.append("description: >")
            lines.append(f"  {val}")
        else:
            lines.append(yaml.dump({key: val}, default_flow_style=False).strip())

    # Remaining fields alphabetically
    for key in sorted(data):
        lines.append(yaml.dump({key: data[key]}, default_flow_style=False).strip())

    lines.append("---")

    result = "\n".join(lines) + "\n"
    if body:
        if not body.startswith("\n"):
            result += "\n"
        result += body

    return result


def read_skill_manifest(skill_dir: Path) -> SkillManifest | None:
    """Read and parse SKILL.md frontmatter from a skill directory.

    Returns None if SKILL.md doesn't exist or has no valid frontmatter.
    """
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.exists():
        skill_file = skill_dir / "skill.md"
    if not skill_file.exists():
        return None

    content = skill_file.read_text(encoding="utf-8")
    manifest, _ = parse_frontmatter(content)
    if not manifest.name:
        return None
    return manifest


def update_skill_source(skill_dir: Path, source: str | None) -> bool:
    """Add or update the source: field in a skill's frontmatter.

    Preserves the body content. Returns True if the file was modified.
    """
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.exists():
        skill_file = skill_dir / "skill.md"
    if not skill_file.exists():
        return False

    content = skill_file.read_text(encoding="utf-8")
    manifest, body = parse_frontmatter(content)

    if not manifest.name:
        return False

    manifest.source = source
    new_content = render_frontmatter(manifest, body)
    skill_file.write_text(new_content, encoding="utf-8")
    return True
