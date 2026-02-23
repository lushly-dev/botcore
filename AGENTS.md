# Botcore - Agent Documentation

Shared bot infrastructure — config, plugin contract, skill registry, and extracted commands for the Lushly ecosystem.

> **!Important:** The year is 2026, not 2025.

## Development Commands

```bash
# Install (editable, with dev deps)
uv pip install --python python --break-system-packages -e ".[dev,mcp]"

# Run all tests
pytest tests/ -v

# Run single test file
pytest tests/test_skill_seed.py -v

# Lint
ruff check src/

# Lint with auto-fix
ruff check src/ --fix
```

## Architecture

```
src/botcore/
├── __init__.py        # Package exports
├── config.py          # botcore.toml / pyproject.toml config loading
├── docs.py            # Doc topic registry
├── plugin.py          # Plugin contract + PluginRegistry
├── registry.py        # Command registry
├── server.py          # MCP server factory (build_namespace, build_docs, create_mcp_server)
├── commands/          # Built-in commands
│   ├── dev/           # Dev commands (lint, test, build, check-*)
│   ├── cdp/           # Chrome DevTools Protocol commands
│   ├── skill/         # Skill registry commands (seed, list, status, lint, adopt, index)
│   ├── docs.py        # Documentation commands
│   ├── info.py        # Workspace/environment info
│   ├── research.py    # Gemini + Google search
│   ├── spec.py        # Spec lifecycle
│   └── undo.py        # Undo history
├── skills/            # 52 bundled universal skills
│   ├── do-commit/     # Action: commit with quality gates
│   ├── do-pr/         # Action: create pull request
│   ├── do-release/    # Action: version and publish
│   ├── do-review/     # Action: review code or PR
│   ├── do-hotfix/     # Action: emergency fix workflow
│   ├── manage-skills/ # Skill management reference
│   └── ...            # 46 more skills
└── utils/             # Shared utilities
    ├── runner.py       # smart_truncate, subprocess helpers
    └── workspace.py    # Workspace discovery
```

## Plugin Contract

Plugins register commands, docs, and skills via entry points:

```python
# In plugin's pyproject.toml
[project.entry-points."botcore.plugins"]
myplugin = "myplugin.plugin:MyPlugin"

# In plugin code
class MyPlugin:
    def register(self, registry):
        registry.add_commands([my_command])
        registry.add_docs("myplugin", DOCS)
        registry.set_mcp_name("myplugin")
        registry.add_skills_dir(Path(__file__).parent / "skills")
```

## Server Factory

```python
from botcore.server import build_namespace, build_docs, create_mcp_server

# Dynamic namespace: core + plugin commands
namespace, registry = build_namespace()

# One-liner MCP server
server = create_mcp_server("botcore", version="0.2.0")
```

## Skill Ownership

Skills use `source:` frontmatter for three-tier ownership:
- **`source: botcore`** — Bundled, updated by `skill_seed --update`
- **`source: <plugin>`** — Plugin-provided
- **No source / `source: local`** — Project-specific, never overwritten

## Configuration

Per-repo config in `botcore.toml` or `pyproject.toml [tool.botcore]`:

```toml
[skills]
include = ["security", "testing"]  # Only seed these
skip = ["i18n"]                    # Exclude these
source_dir = ".claude/skills"      # Target directory
```

## Conventions

- Python 3.11+ minimum
- Tests in `tests/` directory (`test_*.py`)
- Ruff for linting (line-length 100, py311 target)
- Hatchling build backend
- Skills bundled as markdown in `src/botcore/skills/`

## Git Hooks (Lefthook)

Lefthook manages git hooks. Requires `lefthook` binary on PATH.

| Hook | Commands | Trigger |
|------|----------|--------|
| pre-commit | ruff check --fix (staged), ruff format (staged), portability, file-size | `git commit` |
| pre-push | Full ruff lint, format-check, pytest, portability, file-size | `git push` |
| check | Same as pre-push | `lefthook run check` |

**Check scripts** (`scripts/`):

| Script | What it checks |
|--------|---------------|
| `check-file-size.mjs` | Warn >300, error >500 lines. Escape: `# botcore-override: max-lines=N` (cap 1000) |
| `check-portability.mjs` | Machine-specific paths (drive letters, user homes). Escape: `# portability-ok: reason` |

Skip hooks: `git commit --no-verify` / `git push --no-verify`
