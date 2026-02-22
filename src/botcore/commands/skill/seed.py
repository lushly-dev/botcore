"""Seed skills into a project's .claude/skills/ directory."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from afd import CommandResult, error, success

from botcore.commands.skill._discovery import discover_available_skills, discover_local_skills
from botcore.commands.skill.frontmatter import (
    parse_frontmatter,
    render_frontmatter,
)
from botcore.config import load_config
from botcore.utils.workspace import find_workspace

logger = logging.getLogger(__name__)


async def skill_seed(
    update: bool = False,
    dry_run: bool = False,
    plugin_dirs: list[Path] | None = None,
) -> CommandResult[dict]:
    """Seed available skills into the project's skills directory.

    Algorithm:
    1. Load config → get SkillsConfig (include/skip/source_dir/agent_skills)
    2. discover_available_skills() → all candidates from botcore + plugins
    3. Filter by include/skip (include takes priority; if set, skip is ignored)
    4. For each skill:
       - Not present locally → copy tree, inject source: in frontmatter
       - Present, matching source: → overwrite if update=True, skip otherwise
       - Present, no source: or different → skip (log warning)
    5. If agent_skills=True, mirror to .agent/skills/
    6. Return summary
    """
    ws = find_workspace()
    if not ws:
        return error(
            "NO_WORKSPACE",
            "Could not find workspace root",
            suggestion="Run from within a Git repository",
        )

    config = load_config(workspace=ws)
    skills_config = config.skills
    skills_dir = ws / skills_config.source_dir
    available = discover_available_skills(plugin_dirs)

    if not available:
        return error("NO_SKILLS_AVAILABLE", "No skills found in any source")

    # Filter
    candidates = _filter_skills(available, skills_config.include, skills_config.skip)
    local = discover_local_skills(skills_dir)

    seeded: list[str] = []
    updated: list[str] = []
    skipped: list[dict] = []

    for name, skill in sorted(candidates.items()):
        if name in local:
            local_path, local_manifest = local[name]
            local_source = local_manifest.source if local_manifest else None

            if local_source and local_source != skill.source:
                skipped.append({"name": name, "reason": f"owned by {local_source}"})
                continue

            if local_source == skill.source and update:
                if not dry_run:
                    _copy_skill(skill.source_path, local_path, skill.source)
                updated.append(name)
            else:
                reason = "already present" if not local_source else "up to date"
                if not local_source:
                    reason = "unmanaged (use skill_adopt first)"
                skipped.append({"name": name, "reason": reason})
        else:
            target = skills_dir / name
            if not dry_run:
                skills_dir.mkdir(parents=True, exist_ok=True)
                _copy_skill(skill.source_path, target, skill.source)
            seeded.append(name)

    # Mirror to .agent/skills/ if configured
    agent_mirrored = 0
    if skills_config.agent_skills and not dry_run:
        agent_dir = ws / ".agent" / "skills"
        agent_dir.mkdir(parents=True, exist_ok=True)
        for name in seeded + updated:
            src = skills_dir / name
            dst = agent_dir / name
            if src.is_dir():
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
                agent_mirrored += 1

    return success(
        data={
            "seeded": seeded,
            "updated": updated,
            "skipped": skipped,
            "agent_mirrored": agent_mirrored,
            "dry_run": dry_run,
        }
    )


def _filter_skills(
    available: dict,
    include: list[str] | None,
    skip: list[str],
) -> dict:
    """Filter skills by include/skip. Include takes priority."""
    if include is not None:
        return {k: v for k, v in available.items() if k in include}
    return {k: v for k, v in available.items() if k not in skip}


def _copy_skill(source_path: Path, target_path: Path, source_name: str) -> None:
    """Copy a skill directory and inject source: into frontmatter."""
    if target_path.exists():
        shutil.rmtree(target_path)
    shutil.copytree(source_path, target_path)

    # Inject source: into frontmatter
    skill_file = target_path / "SKILL.md"
    if not skill_file.exists():
        skill_file = target_path / "skill.md"
    if not skill_file.exists():
        return

    content = skill_file.read_text(encoding="utf-8")
    manifest, body = parse_frontmatter(content)
    manifest.source = source_name
    skill_file.write_text(render_frontmatter(manifest, body), encoding="utf-8")
