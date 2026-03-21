# Botcore Roadmap

> Long-term feature trajectory. Active work tracked in `docs/features/active/`. Proposals in `docs/features/proposed/`.

## Current State (Phase 1 — Complete)

Core infrastructure, plugin system, and initial plugin packages are functional:

- **Core** — Config, plugin registry, MCP server factory, 24+ built-in commands (dev, skill, cdp, docs, info, research, spec, undo)
- **Agents** — AgentOrchestrator with lifecycle management, task assignment, health tracking (sync execution)
- **LLM** — Session management, command-to-tool bridging, permission gates
- **Memory** — JSON file store with three-tier scoped access control (agent/team/task), contextvar enforcement
- **Connectors** — GitHub connector with dual rate-limit tracking, ConnectorBase middleware stack (248 tests)
- **Teams** — Bot interface with tenant auth, intent dispatch, Adaptive Card rendering

## Foundation (Next — Pre-Phase-2)

Architectural interfaces that must exist before expanding agent or connector features. These are cheap to implement now and expensive to retrofit later.

| Spec | Why Foundation | Status |
|------|----------------|--------|
| [Agent Capability Declarations](docs/features/complete/agent-capability-declarations/spec.md) | Shipped. Agents now resolve tools from `skills` plus scoped connector access via `connectors` / `connector_commands`. | Complete |
| [Per-Agent Permission Profiles](docs/features/active/per-agent-permissions/spec.md) | Without this, every agent gets same shell/filesystem permissions. Move permission gates from session to AgentConfig. | Active |
| [Orchestrator State Serialization](docs/features/complete/orchestrator-state-serialization/spec.md) | Shipped. Orchestrator state now supports versioned snapshots, restore-safe recovery, resumable pending tasks, and opt-in autosave. | Complete |

## AFD 0.6.0 Adoption

Cross-cutting adoption of AFD 0.6.0 capabilities. Seven work items, independently implementable.

| Work Item | Priority | Depends On | Status |
|-----------|----------|------------|--------|
| [Testing Helpers](docs/features/complete/afd-060-adoption/spec.md#p1-testing-helpers) | P1 | — | Complete |
| [Middleware Stack](docs/features/complete/afd-060-adoption/spec.md#p2-middleware-stack-integration) | P2 | — | Complete |
| [Telemetry](docs/features/complete/afd-060-adoption/spec.md#p3-telemetry-integration) | P3 | P2 | Complete |
| [Richer CommandResult Fields](docs/features/complete/afd-060-adoption/spec.md#p4-richer-commandresult-fields) | P4 | — | Complete |
| [Pipelines](docs/features/complete/afd-060-adoption/spec.md#p5-directclient-pipelines) | P5 | P2 (soft) | Complete |
| [Batch Execution](docs/features/complete/afd-060-adoption/spec.md#p6-batch-execution) | P6 | P2 (soft) | Complete |
| [Streaming](docs/features/complete/afd-060-adoption/spec.md#p7-streaming-deferred) | P7 | — | Deferred |

See [full spec](docs/features/complete/afd-060-adoption/spec.md) for architecture, contracts, and implementation details.

## Phase 2 — Proposed

Features that the plugin architecture supports adding without rearchitecture. Each is additive — no changes to CommandResult, plugin protocol, or core.

| Proposal | Category | Effort |
|----------|----------|--------|
| [Async Task Execution](docs/features/proposed/async-task-execution/proposal.md) | Agents | Medium |
| [Cost-Aware Routing](docs/features/proposed/cost-aware-routing/proposal.md) | Agents | Small-Medium |
| [SQLite Memory Backend](docs/features/proposed/sqlite-memory-backend/proposal.md) | Memory | Medium |
| [Azure Connectors](docs/features/proposed/azure-connectors/proposal.md) | Connectors | Medium |

## Future — Longer Term

Features on the horizon that don't need detailed specs yet. Listed for directional alignment.

### Connectors

- **Graph API connector** — Microsoft Graph for users, calendar, mail. Same ConnectorBase pattern as GitHub/Azure.
- **ServiceNow / Jira connectors** — Enterprise ticketing. Same pattern.
- **Custom webhook connector** — Generic HTTP connector for arbitrary APIs with user-defined schema.

### Channels

- **Slack plugin** — Same pattern as Teams plugin (auth, intent, card rendering).
- **Custom webhook channel** — Inbound/outbound webhooks for arbitrary integrations.

### Memory

- **Vector embedding search** — sqlite-vec or Azure AI Search for semantic memory queries. Same store interface, different backend.
- **Memory-as-context-backing-store** — Pruned context topics archived to memory, retrievable on demand. Depends on SDK exposing context management hooks.

### Agent Orchestration

- **Distributed agent pool** — Multi-process/multi-machine orchestration via shared state backend (Redis, Postgres). Orchestrator interface stays the same — state backend changes.
- **Persistent gateway** — Long-running orchestrator process that survives across MCP sessions. Builds on state serialization.
- **Agent role templates** — Preconfigured roles (researcher, coder, reviewer) with default connectors, permissions, and system prompts.

### Security

- **Plugin trust model** — Signing and verification for third-party plugins. Matters when the plugin ecosystem grows beyond first-party packages.
- **Connector-level approval workflows** — Destructive operations (delete repo, merge PR) require human approval before execution.
- **Container sandbox plugin** — Optional `botcore-sandbox` for running untrusted agent code in containers. Connector interface stays identical.

### Surfaces

- **Web dashboard** — CommandResult-powered UI for agent health, task progress, memory contents. No API translation layer — same commands.
- **Mobile surface** — Same commands via mobile-optimized rendering.

### Developer Experience

- **Config migration system** — Versioned config with auto-migration as botcore evolves. Matters when config complexity grows.
- **Skill research command** — Auto-generate skill drafts from external documentation. See [proposal](docs/features/proposed/skill-research/proposal.md).

## Non-Goals

Things botcore explicitly does not intend to build:

- **Messaging channel runtime** — Botcore is not a chat gateway. Channel plugins (Teams, Slack) handle protocol translation, not session management.
- **Model runtime** — The Copilot SDK handles context compaction, streaming, multi-model, tool calling, auth. Botcore builds above the SDK, not alongside it.
- **Consumer product** — Botcore is developer infrastructure. "Install and use" is OpenClaw/NanoClaw territory.
- **Topic-chunked context management** — This requires SDK-level hooks for custom compaction that don't exist today. If the SDK exposes this surface, it becomes viable.
