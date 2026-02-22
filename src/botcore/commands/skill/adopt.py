"""Adopt an unmanaged skill — add source: to its frontmatter."""

from __future__ import annotations

from afd import CommandResult, error, success

from botcore.commands.skill.frontmatter import read_skill_manifest, update_skill_source
from botcore.config import load_config
from botcore.utils.workspace import find_workspace


async def skill_adopt(
    name: str,
    source: str = "local",
) -> CommandResult[dict]:
    """Claim an unmanaged skill by adding source: to its frontmatter.

    Fails if:
    - Skill directory doesn't exist
    - Skill has no SKILL.md
    - Skill already has a different source:
    """
    ws = find_workspace()
    if not ws:
        return error(
            "NO_WORKSPACE",
            "Could not find workspace root",
            suggestion="Run from within a Git repository",
        )

    config = load_config(workspace=ws)
    skills_dir = ws / config.skills.source_dir
    skill_dir = skills_dir / name

    if not skill_dir.is_dir():
        return error(
            "SKILL_NOT_FOUND",
            f"Skill directory not found: {name}",
            suggestion=f"Check that {skills_dir / name} exists",
        )

    manifest = read_skill_manifest(skill_dir)
    if manifest is None:
        return error(
            "NO_MANIFEST",
            f"No valid SKILL.md found in {name}",
            suggestion="Ensure the skill has a SKILL.md with YAML frontmatter",
        )

    if manifest.source is not None and manifest.source != source:
        return error(
            "SOURCE_CONFLICT",
            f"Skill '{name}' already owned by '{manifest.source}', cannot adopt as '{source}'",
            suggestion=f"Remove the source: field first or use source='{manifest.source}'",
        )

    if manifest.source == source:
        return success(
            data={"name": name, "source": source, "changed": False},
            reasoning=f"Skill already has source: {source}",
        )

    updated = update_skill_source(skill_dir, source)
    return success(data={"name": name, "source": source, "changed": updated})
