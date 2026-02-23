# Contributing to Botcore

Botcore is the shared bot infrastructure for the Lushly ecosystem — config loading, the plugin contract, skill registry, and extracted commands that any bot can use. If you're contributing, you're building reusable primitives for agents.

## Prerequisites

- **Python** >= 3.11
- **uv** (recommended) or **pip**
- **Node.js** (for Lefthook git hooks and hygiene scripts)

## Getting Started

```bash
git clone https://github.com/lushly-dev/botcore.git
cd botcore
uv pip install --python python --break-system-packages -e ".[dev,mcp]"
pytest tests/ -v
```

Install Lefthook for git hooks:

```bash
lefthook install
```

## Architecture at a Glance

```
src/botcore/
├── config.py          # botcore.toml / pyproject.toml config loading
├── plugin.py          # Plugin contract + PluginRegistry
├── registry.py        # Command registry
├── server.py          # MCP server factory (3 meta-tool pattern)
├── docs.py            # Doc topic registry
├── commands/          # Built-in commands (dev, cdp, skill, docs, research, spec, undo)
├── skills/            # 52 bundled universal skills (markdown)
└── utils/             # smart_truncate, subprocess helpers, workspace discovery
```

## How to Contribute

### Adding a Command

All commands are async functions that return `CommandResult`. Use `success()` and `error()` from the AFD package:

```python
from afd.core.result import success, error

async def my_command(path: str = ".") -> dict:
    """Imperative verb description of what this does."""
    result = do_work(path)
    if not result:
        return error(
            code="NOT_FOUND",
            message="No items found",
            suggestion="Check the path exists and contains source files"
        )
    return success({"items": result}, reasoning="Scanned 42 files")
```

Key rules:
- Every error **must** include a `suggestion` for agent self-recovery
- Descriptions start with an imperative verb
- Commands go in `src/botcore/commands/` under the appropriate subdirectory
- Register commands in the relevant module's `__init__.py`

### Building a Plugin

Plugins are the primary extension mechanism. Implement the `BotCorePlugin` protocol:

```python
class MyPlugin:
    def register(self, registry):
        registry.add_commands([my_command])
        registry.add_docs("myplugin", DOCS)
        registry.set_mcp_name("myplugin")
        registry.add_skills_dir(Path(__file__).parent / "skills")
```

Register via entry point in your plugin's `pyproject.toml`:

```toml
[project.entry-points."botcore.plugins"]
myplugin = "myplugin.plugin:MyPlugin"
```

Plugins auto-discover via entry points — no manual wiring needed.

### Adding or Modifying Skills

Skills are markdown files in `src/botcore/skills/`. They use three-tier ownership:

| Source | Meaning | Updated by |
|--------|---------|------------|
| `source: botcore` | Bundled with botcore | `skill_seed --update` |
| `source: <plugin>` | Provided by a plugin | Plugin releases |
| `source: local` / none | Project-specific | Manual edits only |

When editing bundled skills, update the skill's markdown file directly. The `SKILL.md` format has required frontmatter — see existing skills for examples.

### MCP Server

Botcore exposes a 3 meta-tool MCP server via `create_mcp_server()`:

| Tool | Purpose |
|------|---------|
| `botcore-start` | Discovery — available commands and capabilities |
| `botcore-docs` | Reference documentation by topic |
| `botcore-run` | Execute Python code with all botcore functions available |

Run it:

```bash
python -m botcore.server          # stdio transport
python -m botcore.server --sse    # SSE transport
```

### Configuration

Per-repo config lives in `botcore.toml` or `pyproject.toml [tool.botcore]`:

```toml
[skills]
include = ["security", "testing"]  # Only seed these
skip = ["i18n"]                    # Exclude these
source_dir = ".claude/skills"      # Target directory
```

When modifying config loading, update `src/botcore/config.py` and add tests in `tests/test_config.py`.

## Quality Gates

### Lefthook Git Hooks

**Pre-commit** (every commit):
- Ruff lint + auto-fix on staged `.py` files
- Ruff format on staged `.py` files
- Portability check (no machine-specific paths)
- File size check (warn >300 lines, error >500)

**Pre-push** (before push):
- Full Ruff lint + format check
- Full test suite (`pytest tests/ -v --tb=short`)
- Portability + file size on all files

**On-demand quality gate**:

```bash
lefthook run check   # Lint + format + test + portability + file-size
```

### Development Commands

```bash
# Tests
pytest tests/ -v                       # All tests
pytest tests/test_config.py -v         # Single file
pytest tests/ -v --tb=short -x         # Stop on first failure

# Lint
ruff check src/                        # Check
ruff check src/ --fix                  # Auto-fix
ruff format src/                       # Format
ruff format --check src/               # Format check
```

## Code Style

Enforced by Ruff:

- **Line length**: 100 characters
- **Target**: Python 3.11
- **Rules**: pyflakes, pycodestyle, isort, pyupgrade, McCabe complexity (max 20)
- **Max function args**: 8
- **Max branches**: 20

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add plugin registry validation
fix: handle missing config gracefully
docs: update plugin setup guide
test: add coverage for skill seeding
```

## Submitting Changes

1. Create a branch from `main`
2. Make changes following the patterns above
3. Verify locally:
   - `ruff check src/` — no lint errors
   - `ruff format --check src/` — formatting clean
   - `pytest tests/ -v` — all tests pass
4. Push and open a pull request

### PR Guidelines

- Keep PRs focused on a single concern
- Include tests for new commands and config changes
- Update `AGENTS.md` if adding commands or changing architecture
- All Lefthook hooks must pass

## Further Reading

- [AGENTS.md](AGENTS.md) — Architecture, plugin contract, skill ownership, server factory
- [CHANGELOG.md](CHANGELOG.md) — Release history

## Need Help?

Use GitHub Discussions for questions and design conversations.