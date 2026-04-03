---
name: botcore-architecture
source: botcore
description: >
  Botcore system architecture — component topology, data flow, security boundaries, and extension
  points. Covers core package structure, plugin registry flow, MCP server factory, agent orchestrator,
  memory subsystem, connector middleware stack, and cross-cutting concerns (audit, auth, config).
  Use when understanding how components connect, tracing request flow, planning new plugins or
  connectors, debugging integration issues, or reviewing architecture decisions. Triggers: architecture,
  component, data flow, request flow, middleware, plugin registry, MCP factory, orchestrator topology,
  connector stack, system diagram, how does botcore work.

version: 1.0.0
triggers:
  - architecture
  - component
  - data flow
  - request flow
  - middleware
  - plugin registry
  - MCP factory
  - orchestrator topology
  - connector stack
  - system diagram
  - how does botcore work
  - package structure
  - extension point
portable: true
---

# Botcore Architecture

System architecture for botcore — component topology, data flow, security boundaries, and extension points.

## System Topology

```
┌─────────────────────────────────────────────────────────┐
│ Surfaces (consumers of commands)                         │
│ ┌─────────┐ ┌─────────┐ ┌──────────┐ ┌──────────────┐  │
│ │   CLI   │ │   MCP   │ │ DirectCli│ │ Teams / Slack│  │
│ └────┬────┘ └────┬────┘ └────┬─────┘ └──────┬───────┘  │
│      │           │           │               │          │
│      └───────────┴─────┬─────┴───────────────┘          │
│                        │                                 │
│              ┌─────────▼──────────┐                      │
│              │  Command Registry  │ ◄── flat namespace   │
│              │  (all commands)    │                      │
│              └─────────┬──────────┘                      │
│                        │                                 │
│    ┌───────────────────┼───────────────────┐             │
│    │                   │                   │             │
│    ▼                   ▼                   ▼             │
│ ┌──────┐        ┌──────────┐       ┌────────────┐       │
│ │ Core │        │ Plugins  │       │ Connectors │       │
│ │ cmds │        │ (agents, │       │ (GitHub,   │       │
│ │      │        │  llm,    │       │  Azure,    │       │
│ │ dev/ │        │  memory) │       │  Graph)    │       │
│ │ skill│        │          │       │            │       │
│ │ cdp/ │        │          │       │            │       │
│ └──────┘        └──────────┘       └─────┬──────┘       │
│                                          │              │
│                              ┌───────────▼───────────┐  │
│                              │  ConnectorBase         │  │
│                              │  (retry, rate-limit,   │  │
│                              │   audit, error map)    │  │
│                              └───────────┬───────────┘  │
│                                          │              │
│                                          ▼              │
│                                    External APIs        │
└─────────────────────────────────────────────────────────┘
```

## Package Map

| Package | Install | Purpose | Dependencies |
|---------|---------|---------|--------------|
| `botcore` | `pip install botcore` | Core: config, plugin registry, MCP factory, built-in commands (dev, skill, cdp, docs, info, research, spec, undo) | None (standalone) |
| `botcore-llm` | `pip install botcore-llm` | LLM sessions, command-to-tool bridging, permission gates | botcore |
| `botcore-agents` | `pip install botcore-agents` | Agent orchestrator, task assignment, lifecycle management | botcore, botcore-llm |
| `botcore-memory` | `pip install botcore-memory` | Scoped key-value store with access control (agent/team/task) | botcore |
| `botcore-connectors` | `pip install botcore-connectors` | Typed HTTP connectors for external services (GitHub done, Azure/Graph planned) | botcore |
| `botcore-teams` | `pip install botcore-teams` | Microsoft Teams bot interface (auth, intent, cards) | botcore |

## Request Flow

### MCP Surface (primary path)

```
Agent (Copilot, Claude, etc.)
  │
  ▼ calls MCP tool
┌──────────────────────────────────┐
│ MCP Server (3 meta-tools)        │
│                                  │
│ {name}-start → discovery JSON    │
│ {name}-docs  → topic reference   │
│ {name}-run   → execute command   │
│                                  │
│ server.py::create_mcp_server()   │
└──────────┬───────────────────────┘
           │ resolves command name
           ▼
┌──────────────────────────────────┐
│ Command Registry (flat dict)     │
│ build_namespace() merges:        │
│   core commands + plugin cmds    │
└──────────┬───────────────────────┘
           │ calls async command function
           ▼
┌──────────────────────────────────┐
│ Command Function                 │
│  - Pydantic input validation     │
│  - Business logic                │
│  - Returns CommandResult[T]      │
└──────────────────────────────────┘
```

### Agent Orchestration Flow

```
task_assign(description, role="researcher")
  │
  ▼
┌──────────────────────────────────┐
│ AgentOrchestrator                │
│  1. Route by name or role        │
│  2. Check agent state (idle?)    │
│  3. Create Task (pending)        │
│  4. Assign → agent state = busy  │
└──────────┬───────────────────────┘
           │
           ▼
┌──────────────────────────────────┐
│ LLM Session (via botcore-llm)    │
│  - bridge_commands() converts    │
│    botcore cmds → Copilot tools  │
│  - Permission gates enforce      │
│    allow_shell/filesystem/mcp    │
│  - Chat loop until task done     │
└──────────┬───────────────────────┘
           │
           ▼
  Task status: completed | failed
  AgentHealth updated (tasks_completed++)
```

### Connector Call Flow

```
github_create_issue(owner, repo, title, body)
  │
  ▼ Pydantic validation (size, format, path traversal check)
  │
  ▼ Scope check (is this agent allowed this connector?)
  │
  ▼ GitHubConnector._api_call("POST", "/repos/{owner}/{repo}/issues", ...)
  │
  ▼ ConnectorBase middleware stack:
    ┌─────────────────────────────┐
    │ 1. Telemetry (trace ID)     │
    │ 2. Logging (sanitized)      │
    │ 3. Rate Limit (semaphore)   │
    │ 4. Retry (exp. backoff)     │
    │ 5. HTTP Client (httpx)      │
    └─────────────┬───────────────┘
                  │
                  ▼ External API response
                  │
                  ▼ HTTP status → error code mapping
                  │
                  ▼ Audit log entry written
                  │
  Returns CommandResult[dict] (success or structured error)
```

## Plugin Registration Flow

```python
# 1. Plugin discovered via entry point
# pyproject.toml:
# [project.entry-points."botcore.plugins"]
# my_plugin = "my_package:MyPlugin"

# 2. Plugin instantiated and register() called
class MyPlugin:
    def register(self, registry: PluginRegistry):
        registry.add_commands([cmd_a, cmd_b])     # Commands
        registry.add_docs("myplugin", DOCS)        # Documentation topics
        registry.set_mcp_name("myplugin")           # CLI/MCP namespace
        registry.add_skills_dir(Path(...))          # Bundled skills
        registry.add_middleware(my_middleware)       # Optional middleware

    def config_schema(self):
        return MyConfig                             # Pydantic model

# 3. build_namespace() merges all plugin commands into flat dict
# 4. create_mcp_server() wraps namespace into 3 meta-tools
# 5. Agent discovers commands via {name}-start, executes via {name}-run
```

## Security Boundaries

```
┌─────────────────────────────────────────────────┐
│ Agent Context                                    │
│                                                  │
│  ┌──────────────────────────────────────────┐    │
│  │ Visible: command names, schemas, results │    │
│  │ NOT visible: tokens, credentials, URLs   │    │
│  └──────────────────────────────────────────┘    │
│                                                  │
│  Permission gates (botcore-llm):                 │
│    allow_shell: false (default)                  │
│    allow_filesystem: false (default)             │
│    allow_mcp: true                               │
│    allow_custom_tools: true                      │
│                                                  │
│  Memory isolation (botcore-memory):              │
│    agent scope → only own entries                │
│    team scope → shared by intent                 │
│    task scope → shared by intent                 │
│    contextvar enforced, not advisory             │
│                                                  │
│  Connector boundary:                             │
│    agent calls command → connector → external    │
│    no raw HTTP/shell/filesystem by default       │
│    credentials stay in env vars, never exposed   │
│                                                  │
│  Audit:                                           │
│    every connector call logged with trace_id     │
│    args sanitized (tokens/passwords redacted)    │
│    structured JSON, machine-parseable            │
└─────────────────────────────────────────────────┘
```

## Extension Points

| Extension Point | Mechanism | Example |
|----------------|-----------|---------|
| New commands | Plugin `register()` → `add_commands()` | GitHub connector commands |
| New connectors | Subclass `ConnectorBase` + plugin registration | Azure, Graph, ServiceNow |
| New channel interfaces | Plugin with message handler + card renderer | Teams, Slack, webhooks |
| New memory backends | Implement store interface (set/get/search/delete/list) | SQLite FTS, vector, Azure AI Search |
| Custom middleware | Plugin `register()` → `add_middleware()` | Request logging, auth injection |
| Custom docs | Plugin `register()` → `add_docs()` | Plugin reference documentation |
| Bundled skills | Plugin `register()` → `add_skills_dir()` | Domain-specific agent skills |

## Configuration Flow

```
botcore.toml (or pyproject.toml [tool.botcore])
  │
  ▼ load_config()
  │
  ▼ Language auto-detection (Python/TypeScript/Rust)
  │
  ▼ Apply tool defaults per language
  │
  ▼ Merge: CLI flags > project config > plugin defaults > core defaults
  │
  ▼ Pydantic validation (extra="forbid" → typos caught)
  │
  ▼ BotCoreConfig available to all packages
```

## Agent State Machine

```
                    create_agent()
                         │
                         ▼
                    ┌─────────┐
                    │ stopped │
                    └────┬────┘
                         │ start_agent()
                         ▼
                    ┌─────────┐
              ┌─────│  idle   │◄──────────┐
              │     └────┬────┘           │
              │          │ task assigned   │ task done
              │          ▼                │
              │     ┌─────────┐           │
              │     │  busy   │───────────┘
              │     └────┬────┘
              │          │ unrecoverable error
              │          ▼
              │     ┌─────────┐
              └─────│  error  │
   stop_agent()     └─────────┘
        │
        ▼
   ┌─────────┐
   │ stopped │
   └─────────┘
```

## Key Conventions

- **Namespace is flat** — `github_create_issue`, `memory_get`, `skill_lint` all top-level. No module prefixing.
- **Commands are async** — Every command is `async def`, returns `CommandResult[T]`.
- **One plugin per package** — Split orthogonal concerns into separate packages.
- **Skills have three-tier ownership** — `source: botcore` (bundled), `source: <plugin>` (plugin-provided), `source: local` (project-specific).
- **Skills use noun-first naming** — Three suffix tiers signal the kind of help: bare noun for actions (`commit`, `pr`), noun-role for agents (`code-reviewer`, `mcp-builder`), noun-`learn` for reference (`caching-learn`, `authentication-learn`). See the `skill-manager` skill for full convention.
- **Config is TOML** — `botcore.toml` or `pyproject.toml [tool.botcore]`. Secrets in env vars, never in config files.
