"""botcore-connectors — typed HTTP connectors for botcore."""

from botcore_connectors.auth import (
    AuthConfig,
    CredentialResolver,
    DefaultCredentialResolver,
    TokenCacheEntry,
)
from botcore_connectors.base import ConnectorBase, ConnectorContext

__all__ = [
    "AuthConfig",
    "ConnectorBase",
    "ConnectorContext",
    "CredentialResolver",
    "DefaultCredentialResolver",
    "TokenCacheEntry",
]
