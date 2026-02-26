"""Teams authentication and authorization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from afd.core.result import CommandResult, error


@dataclass(frozen=True)
class TeamsIdentity:
    """Identity extracted from a Teams activity."""

    user_id: str
    user_name: str
    tenant_id: str
    roles: tuple[str, ...] = ("user",)


def validate_tenant(activity_tenant_id: str | None, allowed_tenant_id: str) -> bool:
    """Check whether the activity's tenant is allowed.

    Returns True if the allowed_tenant_id is empty (no restriction)
    or if the activity tenant matches.
    """
    if not allowed_tenant_id:
        return True
    return activity_tenant_id == allowed_tenant_id


def extract_identity(
    activity: dict[str, Any],
    admin_groups: list[str] | None = None,
    user_groups: list[str] | None = None,
) -> TeamsIdentity:
    """Extract a TeamsIdentity from a Bot Framework activity dict.

    Phase 1: roles are always ["user"]. Graph API group lookup
    for admin_groups / user_groups is deferred to Phase 2.
    """
    from_field = activity.get("from", {})
    channel_data = activity.get("channelData", {})
    tenant = channel_data.get("tenant", {})

    return TeamsIdentity(
        user_id=from_field.get("aadObjectId", from_field.get("id", "")),
        user_name=from_field.get("name", ""),
        tenant_id=tenant.get("id", ""),
    )


def create_unauthorized_error() -> CommandResult[Any]:
    """Return a structured error for unauthorized access."""
    return error(
        "UNAUTHORIZED",
        "You are not authorized to use this bot.",
        suggestion="Contact your administrator to request access.",
        retryable=False,
    )
