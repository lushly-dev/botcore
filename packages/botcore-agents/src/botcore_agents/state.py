"""Orchestrator state serialization — snapshot model, backend protocol, JSON backend."""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from .config import AgentsPluginConfig
from .models import AgentState, Task

logger = logging.getLogger(__name__)


class OrchestratorSnapshot(BaseModel):
    """Point-in-time snapshot of the full orchestrator state.

    Uses the real ``AgentState`` and ``Task`` models directly to avoid
    field-loss from parallel snapshot models.
    """

    model_config = ConfigDict(extra="forbid")

    version: str = "1.0"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    config: AgentsPluginConfig
    agents: dict[str, AgentState]
    tasks: dict[str, Task]


@runtime_checkable
class OrchestratorStateBackend(Protocol):
    """Async interface for persisting orchestrator snapshots.

    Construction is backend-specific (file path, DB connection, etc.).
    """

    async def save(self, snapshot: OrchestratorSnapshot) -> None: ...

    async def load(self) -> OrchestratorSnapshot | None: ...


class JsonStateBackend:
    """Persist snapshots as indented JSON files with atomic writes.

    Parameters
    ----------
    path:
        File path for the JSON snapshot.
    retention_hours:
        Snapshots older than this are treated as stale and ignored on load.
        Defaults to 168 (7 days).
    """

    def __init__(self, path: Path, retention_hours: int = 168) -> None:
        self._path = Path(path)
        self._retention_hours = retention_hours

    async def save(self, snapshot: OrchestratorSnapshot) -> None:
        """Write *snapshot* to disk via atomic temp-file + rename."""
        await asyncio.to_thread(self._save_sync, snapshot)

    async def load(self) -> OrchestratorSnapshot | None:
        """Read snapshot from disk, or ``None`` if missing/stale."""
        return await asyncio.to_thread(self._load_sync)

    # -- sync helpers (run inside to_thread) --------------------------------

    def _save_sync(self, snapshot: OrchestratorSnapshot) -> None:
        parent = self._path.parent
        parent.mkdir(parents=True, exist_ok=True)

        json_bytes = snapshot.model_dump_json(indent=2).encode()

        fd, tmp_path = tempfile.mkstemp(dir=parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(json_bytes)
            os.replace(tmp_path, self._path)
        except BaseException:
            # Clean up temp file on any error
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def _load_sync(self) -> OrchestratorSnapshot | None:
        if not self._path.exists():
            return None

        raw = self._path.read_text(encoding="utf-8")
        snapshot = OrchestratorSnapshot.model_validate_json(raw)

        # Reject stale snapshots
        age_hours = (datetime.now(UTC) - snapshot.timestamp).total_seconds() / 3600
        if age_hours > self._retention_hours:
            logger.info(
                "Ignoring stale snapshot (%.1f h old, retention=%d h)",
                age_hours,
                self._retention_hours,
            )
            return None

        return snapshot
