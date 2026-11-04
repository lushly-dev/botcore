# Botcore (deprecated) - Agent Documentation

> **Deprecated. Don't work in this repository.** botcore is developed and released from `lushly-dev/afd` at `endpoints/botcore`. This repository is frozen and will be archived. Read the AFD repository's `AGENTS.md` and `endpoints/botcore/AGENTS.md` instead.

## Where the work goes

| Was here | Change it in AFD | Distribution |
| --- | --- | --- |
| `src/botcore`, `tests`, `docs` | `endpoints/botcore` | `lushly-botcore` |
| `src/botcore/skills` (bundled skills) | `endpoints/botcore/src/botcore/skills` | `lushly-botcore` |
| `botcore-connectors/` | `endpoints/botcore/botcore-connectors` | `botcore-connectors` |
| `packages/botcore-{llm,agents,memory}` | `endpoints/botcore/packages/botcore-{llm,agents,memory}` | `botcore-llm`, `-agents`, `-memory` |
| `plugins/botcore-teams` | `endpoints/botcore/plugins/botcore-teams` | `botcore-teams` |

AFD's copy has diverged since the import from `7d5c54ca`, so code here is stale: don't port changes from it, and don't copy the skills under `.claude/skills`. AFD rewrote the bundled skills and retired the generic ones.

## Don't do here

- **Don't change code, docs or skills.** A fix here can't ship: this repository has no publish workflow, and `lushly-botcore` publishes only from AFD's `publish-botcore.yml` on `botcore-vX.Y.Z` tags.
- **Don't push tags, run `twine upload` or add changesets.** 0.5.0 was the last release from here. The 17 changesets made after it are carried into AFD's `endpoints/botcore/CHANGELOG.md`.
- **Don't open issues or pull requests here.** Open them in `lushly-dev/afd`.

The only changes this repository should still take are to this deprecation notice, and they stop when it is archived. The handoff and its recovery plan are recorded in AFD's `docs/features/active/platform-monorepo/botcore-handoff.md`.
