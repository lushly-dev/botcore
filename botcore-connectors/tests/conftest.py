"""Shared test fixtures for botcore-connectors."""

from __future__ import annotations

import pytest

from botcore_connectors.base import ConnectorBase, ConnectorContext

TEST_BASE_URL = "https://api.test.local"


@pytest.fixture()
def connector_context() -> ConnectorContext:
    """Minimal ConnectorContext with test defaults."""
    return ConnectorContext(
        base_url=TEST_BASE_URL,
        default_headers={"Accept": "application/json"},
        timeout_seconds=5.0,
        max_retries=3,
        jitter_max_seconds=0.0,  # deterministic in tests
    )


@pytest.fixture()
async def connector(connector_context: ConnectorContext) -> ConnectorBase:
    """ConnectorBase wired to the test base URL."""
    c = ConnectorBase(connector_context)
    yield c  # type: ignore[misc]
    await c.close()
