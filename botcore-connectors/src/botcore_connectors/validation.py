"""Input validation helpers for connector commands."""

from __future__ import annotations

import re

from pydantic import BaseModel

MAX_IDENTIFIER_LENGTH = 256
MAX_BODY_SIZE = 65_536
MAX_ITEMS_DEFAULT = 100

_OWNER_REPO_RE = re.compile(r"^[^/]+/[^/]+$")


class InputValidationResult(BaseModel, extra="forbid"):
    """Aggregated result of input validation checks."""

    valid: bool
    violations: list[str] = []


def check_max_length(
    value: str, *, field_name: str, limit: int = MAX_IDENTIFIER_LENGTH
) -> list[str]:
    """Return violations if *value* exceeds *limit* characters."""
    if len(value) > limit:
        return [f"{field_name}: length {len(value)} exceeds limit {limit}"]
    return []


def check_max_body_size(
    value: str | bytes, *, field_name: str, limit: int = MAX_BODY_SIZE
) -> list[str]:
    """Return violations if *value* exceeds *limit* bytes."""
    size = len(value.encode("utf-8")) if isinstance(value, str) else len(value)
    if size > limit:
        return [f"{field_name}: size {size} bytes exceeds limit {limit}"]
    return []


def check_max_items(
    items: list | tuple | set | frozenset,
    *,
    field_name: str,
    limit: int = MAX_ITEMS_DEFAULT,
) -> list[str]:
    """Return violations if *items* count exceeds *limit*."""
    if len(items) > limit:
        return [f"{field_name}: {len(items)} items exceeds limit {limit}"]
    return []


def check_no_path_traversal(value: str, *, field_name: str) -> list[str]:
    """Return violations if *value* contains path traversal sequences."""
    if value == "..":
        return [f"{field_name}: path traversal detected"]
    if "../" in value or "..\\" in value:
        return [f"{field_name}: path traversal detected"]
    return []


def check_owner_repo(value: str, *, field_name: str) -> list[str]:
    """Return violations if *value* is not a valid ``owner/repo`` identifier."""
    if not _OWNER_REPO_RE.match(value):
        return [f"{field_name}: invalid owner/repo format"]
    return []


def validate_inputs(**checks: list[str]) -> InputValidationResult:
    """Aggregate violations from multiple check calls.

    Usage::

        result = validate_inputs(
            repo=check_owner_repo(repo, field_name="repo"),
            path=check_no_path_traversal(path, field_name="path"),
        )
    """
    violations: list[str] = []
    for field_violations in checks.values():
        violations.extend(field_violations)
    return InputValidationResult(valid=len(violations) == 0, violations=violations)
