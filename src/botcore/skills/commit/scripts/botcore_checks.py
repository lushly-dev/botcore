"""Botcore-backed checks for the do-commit quality gate.

Invoked by quality_gate.py as a subprocess:

    python botcore_checks.py <check-size|check-paths|circular-imports|lockfile-drift>

Requires the ``botcore`` package on the running interpreter (the project's
botcore venv, e.g. ``.botcore-venv``) at or after lushly-dev/botcore 2e7df33 —
needs the ``dev_check_*(path=...)`` kwarg and the dist/build exclusion in
check-size. An older botcore is reported as an environment error, not a pass.

check-size and check-paths scan every SOURCE_DIR_CANDIDATES entry that exists
(botcore's own default is ``<workspace>/src`` only, which monorepos lack).
Root-level files such as ``middleware.ts`` and ``*.config.ts`` are outside
these two scans by choice — the lint/typecheck gates cover them.

lockfile-drift: botcore's dev_check_lockfile is warning-only by design (always
``success``); this wrapper reads ``data["drift"]`` so staged lockfile drift
fails the gate instead of passing silently.

Exit codes: 0 = pass, 1 = findings, 2 = environment/layout error.
Run the unit tests with: python -m unittest discover <this directory>
"""

import asyncio
import inspect
import sys
from pathlib import Path

# Scan whichever of these exist. Broad on purpose: single-package repos use
# src/, monorepos use the rest. Existing-but-empty is fine; none existing is
# an environment error (see run_scoped).
SOURCE_DIR_CANDIDATES = (
    "src",
    "packages",
    "apps",
    "api",
    "lib",
    "scripts",
    "tests",
    ".storybook",
)

OLD_BOTCORE_HINT = (
    "botcore too old for this check (needs dev_check_*(path=...) support, "
    "lushly-dev/botcore >= 2e7df33) — update the editable install"
)


def fail_message(result) -> str:
    """Best-effort human-readable message from a failed CommandResult."""
    err = getattr(result, "error", None)
    return getattr(err, "message", None) or (str(err) if err else "failed without error detail")


def run_scoped(fn, cwd: Path | None = None, candidates: tuple = SOURCE_DIR_CANDIDATES) -> int:
    """Run a per-directory check (check-size/check-paths) over existing source dirs.

    Refuses to pass vacuously: if none of the candidate dirs exist (wrong cwd,
    renamed layout), that is an environment error, not a clean bill.
    """
    if "path" not in inspect.signature(fn).parameters:
        print(OLD_BOTCORE_HINT)
        return 2
    root = cwd or Path.cwd()
    dirs = [d for d in candidates if (root / d).is_dir()]
    if not dirs:
        print(
            f"none of {', '.join(candidates)} exist under {root} — "
            "run the quality gate from the repo root"
        )
        return 2
    failed = False
    for d in dirs:
        result = asyncio.run(fn(path=str((root / d).resolve())))
        if not result.success:
            failed = True
            print(f"{d}: {fail_message(result)}")
    return 1 if failed else 0


def run_global(fn) -> int:
    """Run a workspace-wide check (circular-imports/lockfile-drift).

    Treats data["drift"] warnings as failures: dev_check_lockfile is
    warning-only upstream, but a commit gate must fail on staged drift.
    """
    result = asyncio.run(fn())
    if not result.success:
        print(fail_message(result))
        return 1
    data = getattr(result, "data", None) or {}
    if data.get("drift"):
        warnings = data.get("warnings") or []
        for warning in warnings:
            print(warning.get("message", warning) if isinstance(warning, dict) else warning)
        if not warnings:
            print("lockfile drift detected (no detail provided)")
        return 1
    return 0


SCOPED_CHECKS = ("check-size", "check-paths")
GLOBAL_CHECKS = ("circular-imports", "lockfile-drift")


def main(check: str) -> int:
    if check not in SCOPED_CHECKS + GLOBAL_CHECKS:
        print(f"unknown check: {check} (expected one of {sorted(SCOPED_CHECKS + GLOBAL_CHECKS)})")
        return 2

    try:
        from botcore.commands.dev import (
            dev_check_paths,
            dev_check_size,
            dev_circular_imports,
        )
        from botcore.commands.dev.quality import dev_check_lockfile
    except ImportError as exc:
        print(f"botcore not importable ({exc}) — activate the botcore venv")
        return 2

    commands = {
        "check-size": dev_check_size,
        "check-paths": dev_check_paths,
        "circular-imports": dev_circular_imports,
        "lockfile-drift": dev_check_lockfile,
    }
    if check in SCOPED_CHECKS:
        return run_scoped(commands[check])
    return run_global(commands[check])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ""))
