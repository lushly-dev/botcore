---
name: botcore-principles
source: botcore
description: >
  Core design principles and architectural tenets for the botcore ecosystem. Covers the foundational
  decisions that shape all implementation: CommandResult contract, opt-in composability, connector
  boundaries, meta-tool token efficiency, scoped memory, constrained agency, and plugin protocol.
  Use when making implementation decisions, reviewing designs for consistency, evaluating trade-offs,
  or onboarding to the project philosophy. Triggers: principles, design philosophy, why, trade-off,
  decision, architecture decision, CommandResult, connector boundary, composability, constrained agency.

version: 1.0.0
triggers:
  - principles
  - design philosophy
  - why
  - trade-off
  - decision
  - architecture decision
  - CommandResult
  - connector boundary
  - composability
  - constrained agency
  - security model
  - meta-tool
  - scoped memory
  - plugin contract
portable: true
---

# Botcore Design Principles

The foundational decisions that shape every implementation choice in botcore. When in doubt, these principles resolve ambiguity.

## The Core Bet

Botcore is **composable agent infrastructure for developers.** The missing layer between LLM runtimes (Copilot SDK, Claude SDK) and production agent systems is structured composition — typed contracts, coordinated agents, extensible commands. Botcore builds that layer. It doesn't rebuild the runtime.

## Principles

### 1. CommandResult Everywhere

<rules>
Every operation returns `success(data, {reasoning, confidence})` or `failure({code, message, suggestion})`.
Never return unstructured text. Never raise exceptions for expected failure modes.
Every error includes a machine-readable `code` and an agent-actionable `suggestion`.
</rules>

**Why:** This is the foundational differentiator. Agents reason programmatically about outcomes — branch on error codes, follow suggestions, self-recover. UIs render structured data without parsing natural language. Every action is auditable with a typed shape.

**Implication:** If you're writing a command and tempted to return a string, stop. If you're catching an exception and re-raising, return `error()` instead. Expected failures are data, not crashes.

### 2. Opt-In Composability

<rules>
Each layer of complexity is independently optional.
No forced dependencies between packages.
A user with zero plugins gets a useful system. A user with ten plugins gets a powerful one.
</rules>

**The layers:**
1. **Bare core** — `pip install botcore`, write `botcore.toml` → MCP server with project commands
2. **Add agents** — `pip install botcore-llm botcore-agents` → orchestration + task assignment
3. **Add tools** — write a plugin, implement `register()` → commands appear everywhere
4. **Add integrations** — `pip install botcore-connectors` → agents reach external services
5. **Add surfaces** — same commands from web app, Teams, CLI → no API translation layer

**Why:** "What do you want to build?" not "Do you want this product?" Teams adopt incrementally. No forced complexity.

### 3. Connectors as Capability Boundaries

<rules>
Agents access external systems ONLY through connector commands.
LLM → command → connector → backend. Never LLM → backend directly.
Agent capability = which connectors it has access to.
Absence of a connector = absence of capability (not a permission check — the API doesn't exist).
</rules>

**Why:** This is the security model. Revoking a connector removes the capability entirely — no cached credentials, no memorized paths, just a command that no longer exists. The connector is the interception point for logging, rate limiting, audit, approval workflows. Whether the agent runs in-process or in a container, the interface is identical.

**Contrast:** OpenClaw/NanoClaw give agents bash and filesystem access, then try to constrain with blocklists or container mounts. Botcore gives agents nothing, then explicitly adds capabilities via connectors. Allowlist > blocklist.

### 4. Constrained Agency is the Feature

<rules>
"It figured it out" is a scary production incident, not a demo win.
Agents do exactly what they're tooled to do, nothing more.
Every action is typed, logged, and revocable.
The flexibility you didn't add doesn't exist.
</rules>

**Why:** Enterprise context. Compliance needs to explain what happened. Security needs to trace the access path. Incident review needs to prevent recurrence. Connector-bounded agents give you all three. The "less flexibility" of the connector model is the selling point.

### 5. Meta-Tool Pattern for Token Efficiency

<rules>
All commands collapse into exactly 3 MCP tools regardless of command count:
- `{name}-start` — discovery (version, available functions, topics)
- `{name}-docs` — on-demand reference by topic
- `{name}-run` — execute any command
30 commands = same MCP token cost as 1 command.
</rules>

**Why:** Each MCP tool schema costs tokens in the agent's context window. Naive: 30 commands = 30 tool schemas = context bloat. Meta-tool: 3 tools + on-demand discovery = O(1) overhead. The agent discovers capabilities cheaply, loads docs when needed, executes on demand.

### 6. Protocol Over Inheritance

<rules>
Plugins implement the `BotCorePlugin` protocol — no base class to inherit.
The protocol requires exactly two methods: `register(registry)` and `config_schema()`.
Any class with the right signatures satisfies the protocol.
</rules>

**Why:** Keeps plugins decoupled from botcore internals. Type checkers verify compliance at development time. No fragile base class coupling. No diamond inheritance.

### 7. Scoped Memory with Enforced Access Control

<rules>
Three-tier memory: agent, team, task.
Each agent can only access its own scope unless explicitly granted team scope.
Access control is enforced via contextvars on every operation — not advisory, not optional.
The access model is the hard design decision. Storage backends are swappable.
</rules>

**Why:** Multi-agent teams need isolation by default and sharing by intent. Agent A can't exfiltrate Agent B's findings. Team memory is the intentional sharing surface. The scope hierarchy is foundational — changing it later means rewriting all memory consumers.

### 8. Convention Over Configuration

<rules>
Auto-detect language and apply tool defaults. Only configure what differs.
Empty config sections are valid. Zero-config projects work.
Fail fast on unknown fields (`extra="forbid"` in Pydantic).
Secrets in environment variables, never in TOML.
Config precedence: CLI flags → project config → plugin defaults → core defaults.
</rules>

**Why:** Minimal boilerplate. Sensible defaults. No hidden surprises. Typos cause immediate errors instead of silent misconfiguration.

### 9. One Plugin Per Package, Auditable Size

<rules>
Split orthogonal concerns into separate packages, not overloaded plugins.
Each plugin package should be readable in a sitting (~1-2k LOC).
Bounded blast radius — a vulnerability in one connector affects only that connector's backend.
</rules>

**Why:** Composability is also a security model. Small packages are reviewable before install. Different teams install different plugins. The plugin boundary limits damage.

### 10. Explicit Registration, Visible Surface Area

<rules>
All commands, docs, and skills registered explicitly in `register()` — no auto-discovery within plugins.
Commands enumerated in module `__init__.py`.
Command docstrings start with imperative verbs: "Run X", "Retrieve Y", "Write Z".
</rules>

**Why:** Reviewers and agents can read `register()` to understand the full surface area. No hidden side effects. No magic registration. The plugin contract is the source of truth.

### 11. Defense in Depth for Security

<rules>
Security is layered, not gated:
1. Input validation (Pydantic schemas, size limits, path traversal rejection)
2. Scope enforcement (agent connector list, deny-by-default)
3. Auth isolation (tokens never in CommandResult, metadata, logs, or agent context)
4. Fixed endpoints (connectors MUST NOT construct URLs from user input)
5. Rate limiting (per-connector quotas in ConnectorBase)
6. Audit logging (every call recorded: who, what, when, result, trace_id)
Each layer independently protective. No single point of failure.
</rules>

**Why:** A single security gate can be bypassed. A stack of independent layers requires an attacker to defeat all of them. Input validation catches malformed requests. Scope enforcement catches unauthorized access. Auth isolation prevents credential leaks. Rate limiting prevents abuse. Audit logging enables incident review.

### 12. Noun-First Skill Naming

<rules>
Skills use noun-first naming with three suffix tiers:
- Bare noun for actions: `commit`, `pr`, `release`, `hotfix`
- Noun-role for agent skills: `code-reviewer`, `mcp-builder`, `test-writer`
- Noun-`learn` for reference: `caching-learn`, `authentication-learn`
Never use verb-noun format (`write-tests`, `manage-git`).
</rules>

**Why:** Users think of the noun (domain) first, not the verb. The verb space is large and unpredictable, but the noun space maps directly to what you're working on. Noun-first also clusters related skills alphabetically in the `/` menu. The `-learn` suffix distinguishes reference skills from bare-noun actions that could otherwise be ambiguous.

### 13. Don't Rebuild the Runtime

<rules>
The Copilot SDK provides: context compaction, streaming, multi-model, tool calling, auth, permissions, session persistence, hooks, subagents, MCP integration.
Botcore does NOT rebuild these. It builds the application layer the SDK doesn't opinioniate on.
</rules>

**Why:** Building on the runtime means inheriting its improvements for free. Fighting the runtime means maintaining a parallel implementation. When the SDK adds a feature, botcore gets it. When botcore builds above the SDK, it's additive.

## Decision Heuristics

When evaluating a design choice, apply these tests:

| Question | If Yes | If No |
|----------|--------|-------|
| Does it return CommandResult? | Proceed | Refactor to return CommandResult |
| Can I add it without changing existing plugins? | Extend | Reconsider — may need foundation work first |
| Does an agent need shell/filesystem to use it? | Wrong abstraction — wrap in a connector | Proceed |
| Is the security model allowlist or blocklist? | Allowlist → proceed | Blocklist → redesign |
| Can a user skip this entirely? | Opt-in → proceed | Forced → justify or make optional |
| Would a new contributor understand the registration? | Explicit → proceed | Magic → add explicit registration |

## Anti-Patterns

| Anti-Pattern | Principle Violated | Fix |
|---|---|---|
| Returning raw strings from commands | #1 CommandResult Everywhere | Return `success(data)` or `error(code, message, suggestion)` |
| Plugin that requires another plugin | #2 Opt-In Composability | Make dependency optional or merge packages |
| Agent reads `.env` or `~/.ssh/` directly | #3 Connector Boundaries | Create a connector command, never expose filesystem |
| "Smart" agent that discovers internal APIs | #4 Constrained Agency | Only expose explicit connector commands |
| 30 MCP tools for 30 commands | #5 Meta-Tool Pattern | Use `create_mcp_server()` factory |
| Plugin inheriting from `BotCorePluginBase` | #6 Protocol Over Inheritance | Implement protocol, no base class |
| Agent accessing another agent's memory | #7 Scoped Memory | Use team scope for shared data |
| Requiring 20 lines of config for basic use | #8 Convention Over Configuration | Add sensible defaults, make config optional |
| Monolith plugin with 5k LOC | #9 One Plugin Per Package | Split into focused packages |
| Auto-registering commands via decorators | #10 Explicit Registration | Register in `register()` explicitly |
| Naming a skill `write-tests` or `manage-git` | #12 Noun-First Naming | Use `test-writer`, `git-manager` |
