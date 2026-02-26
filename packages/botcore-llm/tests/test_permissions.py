"""Tests for the permission gate."""

from __future__ import annotations

from botcore_llm.config import LlmPermissionsConfig
from botcore_llm.permissions import create_permission_handler


def _make_request(kind: str) -> dict:
    return {"kind": kind, "toolCallId": "tc-1"}


INV_CTX = {"session_id": "s1"}


class TestPermissionDefaults:
    """Default config: shell=False, filesystem=False, mcp=True, custom_tools=True."""

    def setup_method(self):
        config = LlmPermissionsConfig()
        self.handler = create_permission_handler(config)

    def test_shell_denied(self):
        result = self.handler(_make_request("shell"), INV_CTX)
        assert result["kind"] == "denied-by-rules"

    def test_write_denied(self):
        result = self.handler(_make_request("write"), INV_CTX)
        assert result["kind"] == "denied-by-rules"

    def test_read_denied(self):
        result = self.handler(_make_request("read"), INV_CTX)
        assert result["kind"] == "denied-by-rules"

    def test_mcp_allowed(self):
        result = self.handler(_make_request("mcp"), INV_CTX)
        assert result["kind"] == "approved"

    def test_custom_tool_allowed(self):
        result = self.handler(_make_request("custom-tool"), INV_CTX)
        assert result["kind"] == "approved"

    def test_url_denied(self):
        result = self.handler(_make_request("url"), INV_CTX)
        assert result["kind"] == "denied-by-rules"

    def test_unknown_kind_denied(self):
        result = self.handler(_make_request("something-new"), INV_CTX)
        assert result["kind"] == "denied-by-rules"


class TestPermissionOverrides:
    def test_allow_shell(self):
        config = LlmPermissionsConfig(allow_shell=True)
        handler = create_permission_handler(config)
        result = handler(_make_request("shell"), INV_CTX)
        assert result["kind"] == "approved"

    def test_allow_filesystem(self):
        config = LlmPermissionsConfig(allow_filesystem=True)
        handler = create_permission_handler(config)

        assert handler(_make_request("read"), INV_CTX)["kind"] == "approved"
        assert handler(_make_request("write"), INV_CTX)["kind"] == "approved"

    def test_deny_mcp(self):
        config = LlmPermissionsConfig(allow_mcp=False)
        handler = create_permission_handler(config)
        result = handler(_make_request("mcp"), INV_CTX)
        assert result["kind"] == "denied-by-rules"

    def test_deny_custom_tools(self):
        config = LlmPermissionsConfig(allow_custom_tools=False)
        handler = create_permission_handler(config)
        result = handler(_make_request("custom-tool"), INV_CTX)
        assert result["kind"] == "denied-by-rules"
