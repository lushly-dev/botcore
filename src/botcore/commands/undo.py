"""Botcore undo commands — history tracking and rollback instructions."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from afd import CommandResult, success

HISTORY_FILE = Path.home() / ".botcore" / "history.json"


def load_history() -> dict:
    """Load history from file."""
    if not HISTORY_FILE.exists():
        return {}
    try:
        return json.loads(HISTORY_FILE.read_text())
    except Exception:
        return {}


def save_history(action: str, data: dict) -> None:
    """Save action to history."""
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

    history = load_history()
    history["last_action"] = {
        "action": action,
        "timestamp": datetime.now().isoformat(),
        **data,
    }

    HISTORY_FILE.write_text(json.dumps(history, indent=2))


def clear_history() -> None:
    """Clear history file."""
    if HISTORY_FILE.exists():
        HISTORY_FILE.unlink()


async def undo_status() -> CommandResult[dict]:
    """Get undo history status."""
    history = load_history()

    if not history or "last_action" not in history:
        return success(
            data={"has_history": False}, reasoning="No undo history. Nothing to rollback."
        )

    last = history["last_action"]
    action_type = last.get("action", "unknown")
    timestamp = last.get("timestamp", "unknown")

    rollback_commands: list[str] = []

    if action_type == "spec.sync":
        issues = last.get("created_issues", [])
        if issues:
            issue_list = " ".join(str(i) for i in issues)
            rollback_commands.append(f"gh issue close {issue_list}")
    elif action_type == "work.complete":
        issue = last.get("issue", "unknown")
        rollback_commands.extend([
            f"gh issue reopen {issue}",
            f"gh issue edit {issue} --remove-label done",
        ])
    elif action_type == "work.start":
        branch = last.get("branch", "unknown")
        rollback_commands.append(f"git checkout main && git branch -D {branch}")

    return success(
        data={
            "has_history": True,
            "last_action": action_type,
            "timestamp": timestamp,
            "details": last,
            "rollback_commands": rollback_commands,
        }
    )


async def undo_clear() -> CommandResult[dict]:
    """Clear undo history."""
    clear_history()
    return success(data={"cleared": True}, reasoning="History cleared.")
