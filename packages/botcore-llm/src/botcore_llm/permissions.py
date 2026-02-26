"""Permission gate for LLM sessions.

Produces a handler compatible with ``SessionConfig.on_permission_request``
that enforces the :class:`LlmPermissionsConfig` policy.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from copilot import PermissionRequest, PermissionRequestResult

from .config import LlmPermissionsConfig

logger = logging.getLogger(__name__)

# Type alias matching Copilot SDK's _PermissionHandlerFn
PermissionHandlerFn = Callable[
    [PermissionRequest, dict[str, str]],
    PermissionRequestResult | Any,
]

_APPROVED: PermissionRequestResult = {"kind": "approved"}
_DENIED: PermissionRequestResult = {"kind": "denied-by-rules"}


def create_permission_handler(config: LlmPermissionsConfig) -> PermissionHandlerFn:
    """Build a permission handler from the given config.

    The returned function receives a ``PermissionRequest`` and invocation
    context dict, and returns ``{"kind": "approved"}`` or
    ``{"kind": "denied-by-rules"}`` based on the request kind.

    Args:
        config: Permission configuration governing what actions are allowed.

    Returns:
        A permission handler function for ``SessionConfig.on_permission_request``.
    """

    def handler(
        request: PermissionRequest,
        _invocation: dict[str, str],
    ) -> PermissionRequestResult:
        kind = request.get("kind", "")

        if kind == "shell":
            if config.allow_shell:
                return _APPROVED
            logger.debug("Permission denied: shell")
            return _DENIED

        if kind in ("write", "read"):
            if config.allow_filesystem:
                return _APPROVED
            logger.debug("Permission denied: %s", kind)
            return _DENIED

        if kind == "mcp":
            if config.allow_mcp:
                return _APPROVED
            logger.debug("Permission denied: mcp")
            return _DENIED

        if kind == "custom-tool":
            if config.allow_custom_tools:
                return _APPROVED
            logger.debug("Permission denied: custom-tool")
            return _DENIED

        if kind == "url":
            # URL fetch requests — deny by default (no config toggle yet)
            logger.debug("Permission denied: url")
            return _DENIED

        # Unknown kind — deny by default
        logger.warning("Permission denied for unknown kind: %s", kind)
        return _DENIED

    return handler
