# Contributing to botcore

Thanks for your interest in improving botcore.

## Prerequisites

- Python 3.11+
- `uv` recommended, or `pip`

## Getting Started

```bash
git clone https://github.com/lushly-dev/botcore.git
cd botcore
uv pip install --python python --break-system-packages -e ".[dev,mcp]"
```

## Development Workflow

```bash
# Run tests
pytest tests/ -v

# Lint
ruff check src/

# Lint with fixes
ruff check src/ --fix
```

## Pull Requests

1. Create a branch from `main`
2. Keep changes focused and scoped
3. Add or update tests when behavior changes
4. Ensure lint and tests pass
5. Open a PR using the provided template

## Commit Messages

Use Conventional Commits where possible:

- `feat: add plugin registry validation`
- `fix: handle missing config gracefully`
- `docs: update plugin setup guide`

## Need Help?

Use GitHub Discussions for questions and design conversations.