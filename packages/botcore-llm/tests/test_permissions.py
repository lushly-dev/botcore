"""Tests for the permission gate."""

from __future__ import annotations

from pathlib import Path

from botcore_llm.config import LlmPermissionsConfig
from botcore_llm.permissions import (
    _matches_shell_allowlist,
    _path_allowed,
    create_permission_handler,
)


def _make_request(kind: str, **extra: str) -> dict:
    req: dict = {"kind": kind, "toolCallId": "tc-1"}
    req.update(extra)
    return req


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


# ---------------------------------------------------------------------------
# AgentPermissionsConfig model tests
# ---------------------------------------------------------------------------


class TestAgentPermissionsConfig:
    """AgentPermissionsConfig inherits LlmPermissionsConfig and adds allowlists."""

    def test_inherits_llm_permissions(self):
        from botcore_agents.config import AgentPermissionsConfig

        assert issubclass(AgentPermissionsConfig, LlmPermissionsConfig)

    def test_defaults(self):
        from botcore_agents.config import AgentPermissionsConfig

        cfg = AgentPermissionsConfig()
        assert cfg.allow_shell is False
        assert cfg.allow_filesystem is False
        assert cfg.allow_mcp is True
        assert cfg.allow_custom_tools is True
        assert cfg.shell_allowlist is None
        assert cfg.filesystem_paths is None

    def test_custom_allowlists(self):
        from botcore_agents.config import AgentPermissionsConfig

        cfg = AgentPermissionsConfig(
            allow_shell=True,
            shell_allowlist=["git *", "pytest *"],
            allow_filesystem=True,
            filesystem_paths=["./src"],
        )
        assert cfg.shell_allowlist == ["git *", "pytest *"]
        assert cfg.filesystem_paths == ["./src"]


# ---------------------------------------------------------------------------
# Shell allowlist tests
# ---------------------------------------------------------------------------


class TestShellAllowlist:
    def test_simple_match(self):
        assert _matches_shell_allowlist("git status", ["git *"])

    def test_simple_no_match(self):
        assert not _matches_shell_allowlist("rm -rf /", ["git *"])

    def test_multiple_patterns(self):
        allowlist = ["git *", "pytest *", "ruff *"]
        assert _matches_shell_allowlist("pytest tests/", allowlist)
        assert _matches_shell_allowlist("ruff check .", allowlist)
        assert not _matches_shell_allowlist("curl http://evil", allowlist)

    def test_operator_all_segments_match(self):
        assert _matches_shell_allowlist("git status && git diff", ["git *"])

    def test_operator_one_segment_fails(self):
        assert not _matches_shell_allowlist("git status && rm -rf /", ["git *"])

    def test_pipe_operator(self):
        assert not _matches_shell_allowlist("git log | grep secret", ["git *"])

    def test_semicolon_operator(self):
        assert not _matches_shell_allowlist("git status; rm -rf /", ["git *"])

    def test_or_operator(self):
        assert not _matches_shell_allowlist("git status || rm -rf /", ["git *"])

    def test_empty_command(self):
        assert _matches_shell_allowlist("", ["git *"])

    def test_exact_match_pattern(self):
        assert _matches_shell_allowlist("ls", ["ls"])
        assert not _matches_shell_allowlist("ls -la", ["ls"])


# ---------------------------------------------------------------------------
# Filesystem path tests
# ---------------------------------------------------------------------------


class TestFilesystemPaths:
    def test_allowed_path(self, tmp_path: Path):
        allowed = [str(tmp_path / "src")]
        (tmp_path / "src").mkdir()
        assert _path_allowed(str(tmp_path / "src" / "main.py"), allowed)

    def test_denied_path(self, tmp_path: Path):
        allowed = [str(tmp_path / "src")]
        (tmp_path / "src").mkdir()
        assert not _path_allowed(str(tmp_path / "secrets" / "key.pem"), allowed)

    def test_relative_path_resolved(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "src").mkdir()
        allowed = ["./src"]
        assert _path_allowed(str(tmp_path / "src" / "file.py"), allowed)

    def test_multiple_allowed_paths(self, tmp_path: Path):
        (tmp_path / "src").mkdir()
        (tmp_path / "tests").mkdir()
        allowed = [str(tmp_path / "src"), str(tmp_path / "tests")]
        assert _path_allowed(str(tmp_path / "tests" / "test_main.py"), allowed)
        assert not _path_allowed(str(tmp_path / "secrets" / "key.pem"), allowed)

    def test_prefix_collision_rejected(self, tmp_path: Path):
        """Allowed path /src must NOT match /src-secret (prefix collision)."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src-secret").mkdir()
        allowed = [str(tmp_path / "src")]
        assert not _path_allowed(str(tmp_path / "src-secret" / "creds.json"), allowed)


# ---------------------------------------------------------------------------
# Agent name logging (functional)
# ---------------------------------------------------------------------------


class TestAgentNameLogging:
    """Handler with agent_name works correctly (functional, not log-capture)."""

    def test_handler_with_agent_name_denies(self):
        config = LlmPermissionsConfig()
        handler = create_permission_handler(config, agent_name="researcher")
        result = handler(_make_request("shell"), INV_CTX)
        assert result["kind"] == "denied-by-rules"

    def test_handler_with_agent_name_approves(self):
        config = LlmPermissionsConfig(allow_shell=True)
        handler = create_permission_handler(config, agent_name="coder")
        result = handler(_make_request("shell"), INV_CTX)
        assert result["kind"] == "approved"


# ---------------------------------------------------------------------------
# Two-agent profile isolation
# ---------------------------------------------------------------------------


class TestTwoAgentProfiles:
    """Two handlers with different configs enforce independently."""

    def test_independent_enforcement(self):
        from botcore_agents.config import AgentPermissionsConfig

        coder_config = AgentPermissionsConfig(
            allow_shell=True,
            shell_allowlist=["git *", "pytest *"],
        )
        researcher_config = AgentPermissionsConfig(allow_shell=False)

        coder_handler = create_permission_handler(coder_config, agent_name="coder")
        researcher_handler = create_permission_handler(researcher_config, agent_name="researcher")

        shell_req = _make_request("shell", command="git status")

        assert coder_handler(shell_req, INV_CTX)["kind"] == "approved"
        assert researcher_handler(shell_req, INV_CTX)["kind"] == "denied-by-rules"

    def test_allowlist_isolation(self):
        from botcore_agents.config import AgentPermissionsConfig

        coder_config = AgentPermissionsConfig(
            allow_shell=True,
            shell_allowlist=["git *"],
        )
        ops_config = AgentPermissionsConfig(
            allow_shell=True,
            shell_allowlist=["docker *"],
        )

        coder = create_permission_handler(coder_config, agent_name="coder")
        ops = create_permission_handler(ops_config, agent_name="ops")

        git_req = _make_request("shell", command="git status")
        docker_req = _make_request("shell", command="docker ps")

        assert coder(git_req, INV_CTX)["kind"] == "approved"
        assert coder(docker_req, INV_CTX)["kind"] == "denied-by-rules"
        assert ops(git_req, INV_CTX)["kind"] == "denied-by-rules"
        assert ops(docker_req, INV_CTX)["kind"] == "approved"


# ---------------------------------------------------------------------------
# Shell allowlist integration in handler
# ---------------------------------------------------------------------------


class TestShellAllowlistInHandler:
    """End-to-end: handler with allow_shell + shell_allowlist."""

    def test_allowed_command_passes(self):
        from botcore_agents.config import AgentPermissionsConfig

        config = AgentPermissionsConfig(
            allow_shell=True,
            shell_allowlist=["git *", "pytest *"],
        )
        handler = create_permission_handler(config)
        result = handler(_make_request("shell", command="git status"), INV_CTX)
        assert result["kind"] == "approved"

    def test_disallowed_command_denied(self):
        from botcore_agents.config import AgentPermissionsConfig

        config = AgentPermissionsConfig(
            allow_shell=True,
            shell_allowlist=["git *"],
        )
        handler = create_permission_handler(config)
        result = handler(_make_request("shell", command="rm -rf /"), INV_CTX)
        assert result["kind"] == "denied-by-rules"

    def test_no_allowlist_allows_all(self):
        from botcore_agents.config import AgentPermissionsConfig

        config = AgentPermissionsConfig(allow_shell=True, shell_allowlist=None)
        handler = create_permission_handler(config)
        result = handler(_make_request("shell", command="anything"), INV_CTX)
        assert result["kind"] == "approved"


# ---------------------------------------------------------------------------
# Filesystem paths integration in handler
# ---------------------------------------------------------------------------


class TestFilesystemPathsInHandler:
    """End-to-end: handler with allow_filesystem + filesystem_paths."""

    def test_allowed_path_passes(self, tmp_path: Path):
        from botcore_agents.config import AgentPermissionsConfig

        (tmp_path / "src").mkdir()
        config = AgentPermissionsConfig(
            allow_filesystem=True,
            filesystem_paths=[str(tmp_path / "src")],
        )
        handler = create_permission_handler(config)
        result = handler(
            _make_request("read", path=str(tmp_path / "src" / "file.py")),
            INV_CTX,
        )
        assert result["kind"] == "approved"

    def test_disallowed_path_denied(self, tmp_path: Path):
        from botcore_agents.config import AgentPermissionsConfig

        (tmp_path / "src").mkdir()
        config = AgentPermissionsConfig(
            allow_filesystem=True,
            filesystem_paths=[str(tmp_path / "src")],
        )
        handler = create_permission_handler(config)
        result = handler(
            _make_request("write", path=str(tmp_path / "secrets" / "key.pem")),
            INV_CTX,
        )
        assert result["kind"] == "denied-by-rules"

    def test_no_paths_allows_all(self):
        from botcore_agents.config import AgentPermissionsConfig

        config = AgentPermissionsConfig(allow_filesystem=True, filesystem_paths=None)
        handler = create_permission_handler(config)
        result = handler(_make_request("write", path="/any/path"), INV_CTX)
        assert result["kind"] == "approved"
