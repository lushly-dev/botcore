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

## Architecture

```
src/botcore/                    # Core package
├── __init__.py                 # Package exports
├── config.py                   # botcore.toml / pyproject.toml config loading
├── docs.py                     # Doc topic registry
├── plugin.py                   # Plugin contract + PluginRegistry
├── registry.py                 # Command registry
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
│   └── config.py                # LlmConfig
└── tests/

packages/botcore-agents/        # Agent orchestration plugin (Phase 1)
├── src/botcore_agents/
│   ├── __init__.py              # AgentsPlugin
│   ├── commands.py              # agent_create, task_assign, etc.
│   ├── orchestrator.py          # AgentOrchestrator (pool + tasks)
│   ├── models.py                # Task, AgentHealth, AgentState
│   └── config.py                # AgentConfig, AgentsPluginConfig
└── tests/
```

## Plugin Contract

Plugins register commands, docs, and skills via entry points. See [build-botcore-plugins](skills/build-botcore-plugins/) skill for full patterns.

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

Per-repo config in `botcore.toml` or `pyproject.toml [tool.botcore]`. See [configure-botcore](skills/configure-botcore/) skill for full reference.

```toml
[skills]
include = ["security", "testing"]  # Only seed these
skip = ["i18n"]                    # Exclude these
source_dir = ".claude/skills"      # Target directory
```
