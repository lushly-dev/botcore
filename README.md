# botcore

Shared bot infrastructure — config, plugin contract, skill registry, and extracted commands.

## Install

```bash
pip install lushly-botcore
```

## Commands

### Skill Registry

| Command | Description |
|---------|-------------|
| `skill_seed(update, dry_run)` | Copy skills from sources into `.claude/skills/` with `source:` ownership |
| `skill_list(show_source)` | List installed and available skills |
| `skill_status()` | Detect version drift (ok, stale, unmanaged, missing, conflict) |
| `skill_lint(path, strict)` | Lint skills against SK001–SK015 quality rules |
| `skill_adopt(name, source)` | Claim an unmanaged skill by adding `source:` frontmatter |
| `skill_index(write)` | Generate `_index.md` table of contents |

### Dev

| Command | Description |
|---------|-------------|
| `dev_lint(package, fix)` | Run linter (ruff/biome/clippy) |
| `dev_test(package, coverage)` | Run tests (pytest/vitest/cargo) |
| `dev_build(package)` | Build package |
| `dev_skill_lint()` | Lint skills (delegates to `skill_lint`) |
| `dev_check_size(path)` | Check file sizes against thresholds |
| `dev_check_coverage(package)` | Check test coverage |
| `dev_check_deps()` | Check dependency freshness |
| `dev_dead_code()` | Find unused code |
| `dev_circular_imports()` | Detect circular imports |
| `dev_unused_deps()` | Find unused dependencies |
| `dev_dep_graph()` | Generate dependency graph |
| `dev_check_paths()` | Check cross-platform path issues |

### Other

| Command | Description |
|---------|-------------|
| `info_workspace()` | Workspace discovery |
| `info_env()` | Environment info |
| `docs_lint()` | Lint documentation |
| `research_query(query, mode)` | Gemini + Google search |
| `spec_create(name, template)` | Create spec from template |
| `undo_status()` | Show undo history |

## Skill Ownership

Skills use a `source:` field in YAML frontmatter to track ownership:

```yaml
---
name: security
source: botcore
description: Audit code for vulnerabilities.
version: "3.0.0"
triggers:
  - security
  - vulnerability
---
```

Three tiers:
- **`source: botcore`** — Bundled universal skills, updated by `skill_seed --update`
- **`source: <plugin>`** — Plugin-provided skills
- **No source / `source: local`** — Project-specific skills, never overwritten by seed

## Configuration

In `pyproject.toml`:

```toml
[tool.botcore.skills]
include = ["security", "testing"]  # Only seed these (omit for all)
skip = ["i18n"]                    # Exclude these (ignored if include is set)
source_dir = ".claude/skills"      # Target directory
agent_skills = false               # Also mirror to .agent/skills/
```

## Server Factory (Phase 3)

The server factory automatically wires plugin commands into MCP and CLI surfaces:

```python
from botcore.server import build_namespace, build_docs, create_mcp_server

# Dynamic namespace: core commands + all discovered plugin commands
namespace, registry = build_namespace()

# Merged docs: core topics + plugin topics
docs = build_docs(registry)

# One-liner MCP server creation
server = create_mcp_server("lib", version="0.1.0")
server.run(transport="stdio")
```

Adding a command to botcore or a plugin automatically makes it available everywhere — no hardcoded tool lists.

## Plugin Contract

```python
from botcore.plugin import BotCorePlugin, PluginRegistry

class MyPlugin:
    def register(self, registry: PluginRegistry) -> None:
        registry.add_commands([my_command])
        registry.add_docs("myplugin", DOCS_STRING)
        registry.set_mcp_name("myplugin")
        registry.set_cli_name("myplugin")
        registry.add_skills_dir(Path(__file__).parent / "skills")

    def config_schema(self):
        return MyPluginConfig  # Pydantic model or None
```

## Development

```bash
pip install -e ".[dev,mcp]"
pytest tests/ -v
ruff check src/
```
