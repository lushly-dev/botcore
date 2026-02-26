"""botcore-connectors — typed HTTP connectors for botcore."""

from botcore_connectors.audit import AuditLogEntry, AuditLogger, sanitize_args
from botcore_connectors.auth import (
    AuthConfig,
    CredentialResolver,
    DefaultCredentialResolver,
    TokenCacheEntry,
)
from botcore_connectors.base import ConnectorBase, ConnectorContext
from botcore_connectors.config import (
    KNOWN_CONNECTORS,
    AzureBlobConfig,
    AzureQueueConfig,
    ConnectorsConfig,
    EmailConfig,
    GitHubConnectorConfig,
)
from botcore_connectors.errors import (
    audit_write_failed,
    check_scope,
    input_too_large,
    input_validation_failed,
    path_traversal_blocked,
    scope_violation,
)
from botcore_connectors.plugin import ConnectorsPlugin
from botcore_connectors.validation import (
    MAX_BODY_SIZE,
    MAX_IDENTIFIER_LENGTH,
    MAX_ITEMS_DEFAULT,
    InputValidationResult,
    check_max_body_size,
    check_max_items,
    check_max_length,
    check_no_path_traversal,
    check_owner_repo,
    validate_inputs,
)

__all__ = [
    "AuditLogEntry",
    "AuditLogger",
    "AuthConfig",
    "AzureBlobConfig",
    "AzureQueueConfig",
    "ConnectorBase",
    "ConnectorContext",
    "ConnectorsConfig",
    "ConnectorsPlugin",
    "CredentialResolver",
    "DefaultCredentialResolver",
    "EmailConfig",
    "GitHubConnectorConfig",
    "InputValidationResult",
    "KNOWN_CONNECTORS",
    "MAX_BODY_SIZE",
    "MAX_IDENTIFIER_LENGTH",
    "MAX_ITEMS_DEFAULT",
    "TokenCacheEntry",
    "audit_write_failed",
    "check_max_body_size",
    "check_max_items",
    "check_max_length",
    "check_no_path_traversal",
    "check_owner_repo",
    "check_scope",
    "input_too_large",
    "input_validation_failed",
    "path_traversal_blocked",
    "sanitize_args",
    "scope_violation",
    "validate_inputs",
]
