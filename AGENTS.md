# Botcore - Agent Documentation

Shared bot infrastructure — config, plugin contract, skill registry, and extracted commands for the Lushly ecosystem.

> **!Important:** The year is 2026, not 2025.
> **First time?** See [SETUP.md](SETUP.md) for installation, tooling, and environment setup.

## Commands

| Command | Purpose |
|---------|---------|
| `pytest tests/ -v` | Run all tests |
| `pytest tests/test_skill_seed.py -v` | Run single test file |
| `ruff check src/` | Lint check |
| `ruff check src/ --fix` | Auto-fix lint issues |

## CLI

| Command | Purpose |
|---------|---------|
| `botcore init --non-interactive --json` | Agentic setup — creates config, seeds skills, returns JSON |
| `botcore init` | Interactive project setup with prompts |
| `botcore serve` | Start the MCP server (stdio by default) |
| `botcore skill-seed` | Seed bundled skills into `.claude/skills/` |
| `botcore skill-list` | List available and installed skills |
| `botcore skill-status` | Show skill version drift |
| `botcore info` | Show workspace information |
| `botcore changeset-create` | Create a changeset file for the next release |
| `botcore changeset-status` | Show pending changeset files |
| `botcore changeset-consume` | Consume changesets and update CHANGELOG.md |

All commands except `serve` support `--json` for machine-readable output. Exit codes: 0 = success, 1 = error.

## Architecture

```
src/botcore/                    # Core package
├── __init__.py                 # Package exports
├── config.py                   # botcore.toml / pyproject.toml config loading
├── docs.py                     # Doc topic registry
├── plugin.py                   # Plugin contract + PluginRegistry
├── registry.py                 # Command registry
├── cli.py                      # Click CLI entry point (init, serve, skill-*, info)
├── server.py                   # MCP server factory (build_namespace, build_docs, create_mcp_server)
├── commands/                   # Built-in commands
│   ├── dev/                    # Dev commands (lint, test, build, check-*)
│   ├── cdp/                    # Chrome DevTools Protocol commands
│   ├── skill/                  # Skill registry commands (seed, list, status, lint, adopt, index)
│   ├── docs.py                 # Documentation commands
│   ├── info.py                 # Workspace/environment info
│   ├── research.py             # Gemini + Google search
│   ├── spec.py                 # Spec lifecycle
│   └── undo.py                 # Undo history
├── skills/                     # 54 bundled universal skills
│   └── ...
└── utils/                      # Shared utilities
    ├── runner.py                # smart_truncate, subprocess helpers, retry_async
    └── workspace.py             # Workspace discovery

packages/botcore-llm/           # LLM runtime plugin
├── src/botcore_llm/
│   ├── __init__.py              # LlmPlugin
│   ├── commands.py              # llm_session_create, llm_chat, etc.
│   ├── session.py               # SessionRegistry
│   ├── bridge.py                # Command-to-tool bridge
│   ├── client.py                # CopilotClientManager
│   └── config.py                # LlmConfig, LlmPermissionsConfig
└── tests/

packages/botcore-agents/        # Agent orchestration plugin (Phase 1)
├── src/botcore_agents/
│   ├── __init__.py              # AgentsPlugin
│   ├── commands.py              # agent_create, task_assign, state_save, etc.
│   ├── orchestrator.py          # AgentOrchestrator (pool + tasks + capability resolution + state)
│   ├── state.py                 # OrchestratorSnapshot, StateBackend, JsonStateBackend
│   ├── models.py                # Task, AgentHealth, AgentState
│   └── config.py                # AgentConfig, AgentPermissionsConfig, AgentsPluginConfig (skills, connectors, connector_commands)
└── tests/

packages/botcore-memory/        # Memory plugin (Phase 1)
├── src/botcore_memory/
│   ├── __init__.py              # MemoryPlugin
│   ├── commands.py              # memory_set/get/search/delete/list
│   ├── local_store.py           # Local JSON store backend
│   ├── auth.py                  # Scope access helpers
│   └── models.py                # MemoryConfig + MemoryEntry
└── tests/

plugins/botcore-teams/          # Microsoft Teams bot interface (Phase 1)
├── src/botcore_teams/
│   ├── __init__.py              # TeamsPlugin
│   ├── config.py                # TeamsConfig + TeamsRolesConfig
│   ├── intent.py                # Regex intent parser
│   ├── cards.py                 # CommandResult → Adaptive Card v1.4
│   ├── auth.py                  # Tenant/group gate + identity extraction
│   ├── commands.py              # teams_handle_message/card_action
│   └── bot.py                   # TeamsBot + create_app() webhook
└── tests/
```

## Plugin Packages

### botcore-connectors

Typed HTTP connectors for external services. Separate `pip install` package.

```
botcore-connectors/src/botcore_connectors/
├── __init__.py           # Package exports
├── auth.py               # Credential resolution (env var → CLI fallback, token cache)
├── base.py               # ConnectorBase — retry, rate-limiting, telemetry, error mapping
├── config.py             # ConnectorsConfig + per-connector sub-models
├── errors.py             # HTTP status mapping + GitHub-specific error helpers
├── github.py             # GitHubConnector — dual rate-limit tracking, error remap
├── github_commands.py    # 8 GitHub commands + factory
├── plugin.py             # ConnectorsPlugin — BotCorePlugin protocol
└── validation.py         # Input validation helpers, PaginationParams
```

| Status | Detail |
|--------|--------|
| Phase 1 (specs 01-05) | Complete — 248 tests |
| Phase 2 (Azure) | Pending |
| Phase 3 (Graph) | Pending |

Commands: `cd botcore-connectors && uv run pytest tests/ -v` and `uv run ruff check src/ tests/`

## Plugin Contract

Plugins register commands, docs, and skills via entry points. See [build-botcore-plugins](.claude/skills/build-botcore-plugins/) skill for full patterns.

```python
class MyPlugin:
    def register(self, registry):
        registry.add_commands([my_command])
        registry.add_docs("myplugin", DOCS)
        registry.set_mcp_name("myplugin")
        registry.add_skills_dir(Path(__file__).parent / "skills")
        registry.add_middleware(my_middleware)  # optional
```

## Skill Ownership

Skills use `source:` frontmatter for three-tier ownership:
- **`source: botcore`** — Bundled, updated by `skill_seed --update`
- **`source: <plugin>`** — Plugin-provided
- **No source / `source: local`** — Project-specific, never overwritten

## Configuration

Per-repo config in `botcore.toml` or `pyproject.toml [tool.botcore]`. See [configure-botcore](.claude/skills/configure-botcore/) skill for full reference.

```toml
[skills]
include = ["security", "testing"]  # Only seed these
skip = ["i18n"]                    # Exclude these
source_dir = ".claude/skills"      # Target directory
```

## Architecture & Principles

Two skills capture system-level knowledge:

- **[botcore-architecture](.claude/skills/botcore-architecture/)** — System topology, package map, request flows, security boundaries, extension points
- **[botcore-principles](.claude/skills/botcore-principles/)** — 12 design tenets (CommandResult Everywhere, Opt-In Composability, Constrained Agency, Meta-Tool Pattern, etc.)

## Roadmap

See [ROADMAP.md](ROADMAP.md) for the feature trajectory:
- **Foundation (active)** — Agent capability declarations, orchestrator state serialization, per-agent permissions
- **Phase 2 (proposed)** — Async task execution, cost-aware routing, SQLite memory, Azure connectors
- **Specs** live in `docs/features/active/` (in progress) and `docs/features/proposed/` (queued)
