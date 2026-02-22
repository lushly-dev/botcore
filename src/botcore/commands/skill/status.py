"""Skill status — version drift detection."""

from __future__ import annotations

from pathlib import Path

from afd import CommandResult, error, success

from botcore.commands.skill._discovery import discover_available_skills, discover_local_skills
from botcore.config import load_config
from botcore.utils.workspace import find_workspace


async def skill_status(
    plugin_dirs: list[Path] | None = None,
) -> CommandResult[dict]:
    """Show version drift for managed skills.

    Status per skill:
    - ok: local version matches source version
    - stale: local version is behind source
    - unmanaged: local skill has no source: field
    - missing: source skill not installed locally
    - conflict: local skill has a different source: than expected
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

    available = discover_available_skills(plugin_dirs)
    local = discover_local_skills(skills_dir)

    statuses: list[dict] = []

    # Check all available skills
    for name, source_skill in sorted(available.items()):
        if name not in local:
            statuses.append({
                "name": name,
                "source": source_skill.source,
                "source_version": source_skill.manifest.version,
                "local_version": None,
                "status": "missing",
            })
            continue

        _, local_manifest = local[name]
        if local_manifest is None:
            statuses.append({
                "name": name,
                "source": source_skill.source,
                "source_version": source_skill.manifest.version,
                "local_version": None,
                "status": "unmanaged",
            })
            continue

        if local_manifest.source is None:
            statuses.append({
                "name": name,
                "source": source_skill.source,
                "source_version": source_skill.manifest.version,
                "local_version": local_manifest.version,
                "status": "unmanaged",
            })
            continue

        if local_manifest.source != source_skill.source:
            statuses.append({
                "name": name,
                "source": source_skill.source,
                "source_version": source_skill.manifest.version,
                "local_version": local_manifest.version,
                "status": "conflict",
            })
            continue

        if local_manifest.version != source_skill.manifest.version:
            statuses.append({
                "name": name,
                "source": source_skill.source,
                "source_version": source_skill.manifest.version,
                "local_version": local_manifest.version,
                "status": "stale",
            })
        else:
            statuses.append({
                "name": name,
                "source": source_skill.source,
                "source_version": source_skill.manifest.version,
                "local_version": local_manifest.version,
                "status": "ok",
            })

    # Check local-only skills (not in any source)
    for dir_name, (_, local_manifest) in sorted(local.items()):
        name = local_manifest.name if local_manifest else dir_name
        if name not in available and dir_name not in {s["name"] for s in statuses}:
            statuses.append({
                "name": dir_name,
                "source": local_manifest.source if local_manifest else None,
                "source_version": None,
                "local_version": local_manifest.version if local_manifest else None,
                "status": "unmanaged",
            })

    summary = {s: len([x for x in statuses if x["status"] == s]) for s in
                ("ok", "stale", "unmanaged", "missing", "conflict")}

    return success(data={"skills": statuses, "summary": summary})
