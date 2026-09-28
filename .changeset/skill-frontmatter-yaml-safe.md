---
type: fixed
---

**skill** -- `render_frontmatter` now emits valid YAML for triggers and descriptions containing special characters (e.g. `!bash`, `@file`), and `skill_seed`/`skill_adopt` inject `source:` with a minimal line edit instead of rewriting the frontmatter. Fixes `commands-learn` showing as `unmanaged` after a fresh seed and never updating with `skill_seed --update`.
