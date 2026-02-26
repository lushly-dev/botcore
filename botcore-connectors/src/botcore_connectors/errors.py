"""HTTP status-to-error-code mapping for connectors."""

from __future__ import annotations

from typing import Any

from afd import CommandResult, error

# (error_code, suggestion, retryable)
STATUS_CODE_MAP: dict[int, tuple[str, str, bool]] = {
    400: (
        "BAD_REQUEST",
        "Fix request parameters per API docs",
        False,
    ),
    401: (
        "AUTH_FAILED",
        "Re-authenticate; check credentials are valid and not expired",
        False,
    ),
    403: (
        "FORBIDDEN",
        "Check required permissions for this operation",
        False,
    ),
    404: (
        "NOT_FOUND",
        "Verify resource identifier (repo, ID, path)",
        False,
    ),
    409: (
        "CONFLICT",
        "Fetch current state and reconcile",
        False,
    ),
    422: (
        "VALIDATION_ERROR",
        "Review field values against API constraints",
        False,
    ),
    429: (
        "RATE_LIMITED",
        "Automatic retry via middleware; no user action needed",
        True,
    ),
    500: (
        "SERVICE_ERROR",
        "Automatic retry; if persistent, check service status",
        True,
    ),
    502: (
        "SERVICE_ERROR",
        "Automatic retry; if persistent, check service status",
        True,
    ),
    503: (
        "SERVICE_ERROR",
        "Automatic retry; if persistent, check service status",
        True,
    ),
    504: (
        "SERVICE_ERROR",
        "Automatic retry; if persistent, check service status",
        True,
    ),
}

RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})


def map_status_to_error(
    status_code: int,
    response_body: dict[str, Any] | str | None = None,
) -> CommandResult[dict[str, Any]]:
    """Map an HTTP status code to a ``CommandResult`` error.

    Falls back to ``CLIENT_ERROR`` for unknown 4xx and ``SERVICE_ERROR``
    for unknown 5xx.
    """
    if status_code in STATUS_CODE_MAP:
        code, suggestion, retryable = STATUS_CODE_MAP[status_code]
    elif 400 <= status_code < 500:
        code = "CLIENT_ERROR"
        suggestion = "Inspect response body for details"
        retryable = False
    else:
        code = "SERVICE_ERROR"
        suggestion = "Automatic retry; if persistent, check service status"
        retryable = True

    message = f"HTTP {status_code}"
    if isinstance(response_body, dict) and "message" in response_body:
        message = f"HTTP {status_code}: {response_body['message']}"
    elif isinstance(response_body, str) and response_body:
        message = f"HTTP {status_code}: {response_body[:200]}"

    return error(code, message, suggestion=suggestion, retryable=retryable)


def network_error(exc: Exception) -> CommandResult[dict[str, Any]]:
    """Wrap an httpx network/timeout exception into a ``CommandResult``."""
    return error(
        "NETWORK_ERROR",
        f"Network error: {exc}",
        suggestion="Check network connectivity and service availability",
        retryable=True,
    )


def github_auth_missing() -> CommandResult[dict[str, Any]]:
    """No GitHub credentials could be resolved."""
    return error(
        "GITHUB_AUTH_MISSING",
        "No GitHub token found",
        suggestion="Set GH_TOKEN environment variable or run `gh auth login`",
        retryable=False,
    )


def auth_refresh_failed(provider: str) -> CommandResult[dict[str, Any]]:
    """Credential refresh after 401 produced no valid token."""
    return error(
        "AUTH_REFRESH_FAILED",
        f"Failed to refresh credentials for {provider}",
        suggestion=f"Re-authenticate for {provider}; check credentials are valid",
        retryable=False,
    )
