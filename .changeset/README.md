# Changesets

This directory contains changeset files that describe pending changes for the next release.

## Workflow

1. When you make a user-visible change, create a changeset file:
   ```bash
   botcore changeset-create --type added --description "**cli** -- add verbose flag"
   ```
   Or create a file manually: `.changeset/<any-name>.md`

2. At release time, consume all changesets to update CHANGELOG.md:
   ```bash
   botcore changeset-consume --version 1.2.0
   ```

## File Format

```markdown
---
type: added
---

**component** -- description of the change
```

## Valid Types

| Type | Changelog Category |
|------|--------------------|
| `added` | Added |
| `changed` | Changed |
| `deprecated` | Deprecated |
| `removed` | Removed |
| `fixed` | Fixed |
| `security` | Security |

## Rules

- One changeset per logical change (not per commit)
- Write for users, not developers — focus on impact
- Bold the component or area name
- Multiple changesets can exist at once — they merge at release time
- Changeset files are committed to git (not gitignored)
