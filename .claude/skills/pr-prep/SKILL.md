---
name: pr-prep
description: >
  Ready-to-ship orchestrator for the Botcore repo: syncs the base, runs self-review
  plus a fresh read-only reviewer, updates changesets and docs, runs the diff-scoped
  quality gate against the recorded test baseline, commits, pushes, and creates or
  updates the PR. Inspect mode reports readiness without changing anything; quick mode
  reuses existing review evidence. Second stage of the session loop (session-init →
  pr-prep → session-end). Use when inspecting readiness or ready to ship. Triggers:
  prepare pr, prep pr, do-prepare-pr, ready to ship, ship it, open pr, create pr, push
  and open pr, finalize pr, quick pr.
version: 1.0.0
triggers:
  - prepare pr
  - prep pr
  - do-prepare-pr
  - ready to ship
  - ship it
  - open pr
  - finalize pr
  - quick pr
argument-hint: "inspect | quick"
user-invocable: true
---

# PR Prep

Coordinates the ship path. This is an orchestration contract, not a rigid script.
Keep the ordering where it protects correctness: base sync before review, fixes
before the gate, the gate on the final tree, commit after the gate, PR after the
push.

Run the workflow in the harness the session started in. Do not hand steps to another
harness or attribute one harness's work to another.

## Modes

| Argument | What runs |
|---|---|
| `inspect` | Readiness report only. No edits, commit, push, or PR changes (fetching `origin/main` is allowed). |
| _(none)_ | Base sync → review → docs → gate → commit → push → create/update PR → readiness. |
| `quick` | Gate → commit → push → create/update PR. Only with reusable review evidence (see below). |

## Why the gate is explicit here

Two facts about this repo shape the whole flow:

- **Nothing else runs tests.** The only GitHub workflow publishes to PyPI on tags.
  No PR check runs tests, and `main` has no ruleset or required checks. Lefthook
  hooks run only on clones where `lefthook install` was done. The gate in step 4 is
  the only test evidence the PR will have.
- **The full tree is not green on `main`.** Full-tree `ruff check`, `ruff format
  --check`, `check-portability`, and `check-file-size` all report existing debt, and
  some tests fail. A full-tree run cannot tell your regression from that debt. The
  gate is therefore scoped to the diff for static checks and compared to the
  `session-init` baseline for tests.

For the same reasons, do not run the `commit` skill's `quality_gate.py` or its docs
gate here. The quality gate runs full-tree. The docs gate edits `CHANGELOG.md`
directly, which this repo does through changesets instead.

## Readiness facts (all modes)

Derive from commands, never memory:

```bash
git fetch origin '+refs/heads/main:refs/remotes/origin/main'
git status --short                                   # dirty tree + ownership classification
git log --oneline origin/main..HEAD                  # commits to ship (see caveat)
git rev-list --count HEAD..origin/main               # how far behind main
uv run --frozen botcore changeset-status             # pending changesets
gh pr list --state all --head "$(git rev-parse --abbrev-ref HEAD)" --json number,state,url
```

The fetch updates only a remote-tracking ref, so it is allowed even in `inspect`.
If it fails, report the ref as unverified rather than fresh.

Caveat: after a squash merge, "0 commits ahead" and "N commits ahead" are both
ambiguous. If anything is surprising, use the landing check in `session-end`.

Blockers: unrelated or unknown dirty files (classify them, and stop on unknown), an
in-progress git operation, or work that already landed. Do not open a duplicate PR.

## Full mode

### 1. Base sync

```bash
git fetch origin '+refs/heads/main:refs/remotes/origin/main'
base_sha=$(git rev-parse origin/main)
git merge --no-edit "$base_sha"
```

Never stash, because the stash stack is shared across worktrees. Preserve intended
uncommitted work with a WIP commit if needed. If the merge changed `uv.lock` or any
`pyproject.toml`, re-run the environment step of `session-init`. Review happens after
this so conflicts and stale assumptions get reviewed in their final context.

### 2. Review

1. **Self-review.** Apply the `review` skill's self-review dimensions to
   `git diff "$(git merge-base origin/main HEAD)"` plus untracked files.
2. **Fresh reviewer.** Dispatch one fresh reviewer in the session's own harness. Use
   a subagent with read-only tools that follows the `code-reviewer` skill's Fresh
   Agent pattern. Give it the diff command, the acceptance target, and the relevant
   principles from `botcore-principles` (CommandResult everywhere, errors carry a
   `suggestion`, opt-in composability). Do not give it your conclusions.
3. **Converge.** The coordinator fixes findings, and the reviewer never edits. Run
   one broad pass and at most one focused verification pass. A third pass may only
   verify an unresolved BLOCKER. Context compaction, recovery, and base advances
   never reset the pass count.

If no fresh reviewer is available, full preparation is blocked unless the user
explicitly accepts self-review only. The PR body must say which case applies. Record
the reviewer, pass count, tool isolation, findings fixed or declined (with reason),
and residual risk.

### 3. Docs and changeset

- **Changeset** for a user-visible change to anything that ships: the `lushly-botcore`
  package, bundled skills in `src/botcore/skills/`, or a plugin package.

  ```bash
  uv run --frozen botcore changeset-create --type <added|changed|deprecated|removed|fixed|security> \
    --description "**<component>** -- <impact for users>"
  ```

  Changes limited to tests, CI, `scripts/`, or `.claude/` need no changeset. Never
  edit `CHANGELOG.md` by hand; `botcore changeset-consume` writes it at release.
- **Plans.** If a `docs/features/` plan tracks this work, update it in the same PR:
  check off what shipped, add as-built notes, and move the feature folder from
  `proposed/` to `complete/` when it is done. Update `ROADMAP.md` when a roadmap item
  ships.
- **AGENTS.md** changes when commands, package layout, or the architecture tree
  change. It is the only project instruction file. Never add a `CLAUDE.md` or follow
  a bundled skill's "sync CLAUDE.md" step.
- **Skills.** Lint any skill you touched:

  ```bash
  uv run --frozen python -c "import asyncio; from botcore.commands.skill import skill_lint; print(asyncio.run(skill_lint('<name>')))"
  ```

  A bare name resolves under `.claude/skills/`. Pass an absolute path to lint a
  bundled skill in `src/botcore/skills/`.

  Bundled skills in `src/botcore/skills/` ship to consumers. Project-only skills
  live in `.claude/skills/` without a `source:` field, so `skill-seed --update`
  never overwrites them.

### 4. Gate

Run the gate on the final tree, before committing, so the commit is the gated
content. First write the list of files this task changed:

```bash
base=$(git merge-base origin/main HEAD)
list="$(git rev-parse --git-path botcore-session/changed.txt)"
mkdir -p "$(dirname "$list")"
{ git diff --name-only --diff-filter=d "$base"; git ls-files --others --exclude-standard; } \
  | sort -u > "$list"
```

Remove any file you classified as unrelated or unknown from that list. The formatter
rewrites every file in the list, and those files are not yours to edit. Then run:

```bash
grep -E '\.py$' "$list" | tr '\n' '\0' | xargs -0 -r uv run --frozen ruff format
grep -E '\.py$' "$list" | tr '\n' '\0' | xargs -0 -r uv run --frozen ruff check
grep -E '\.py$' "$list" | tr '\n' '\0' | xargs -0 -r node scripts/check-file-size.mjs
grep -E '\.(py|md|ya?ml|toml|json|mjs)$' "$list" | tr '\n' '\0' \
  | xargs -0 -r node scripts/check-portability.mjs

for suite in tests packages/botcore-llm/tests packages/botcore-agents/tests \
    packages/botcore-memory/tests plugins/botcore-teams/tests botcore-connectors/tests; do
  uv run --frozen pytest "$suite" -q; echo "exit $suite $?"
done
```

Pass file lists through `xargs -0`; never expand an unquoted `$var` of paths. zsh
does not word-split, so the scripts receive one newline-joined argument. They
silently drop arguments that are not existing paths, so they check nothing and exit
0, which looks like a pass.

`ruff format` rewrites the listed files, matching what the pre-commit hook would do.
Run all six suites every time. Together they take about 30 seconds, and plugin
suites break on core changes they do not import directly.

Interpreting failures:

- **Static checks on a touched file.** The file may carry violations from before this
  change. Check the base version, for example
  `git show "$base:<path>" | uv run --frozen ruff check --stdin-filename <path> -`.
  Fix pre-existing issues when the fix is small and in scope (`ruff check --fix` for
  fixable rules). Otherwise list them under Verification as pre-existing, with that
  evidence. Never grow a file already over the 500-line limit without a justified
  `# botcore-override: max-lines=N`.
- **Tests.** Compare each `FAILED`/`ERROR` id and each suite's exit code with
  `$(git rev-parse --git-path botcore-session/baseline.txt)`. Any failure not listed
  there is a regression and must be fixed. A baseline failure that now passes is
  worth a line in the PR.
- **Base moved since the baseline.** Step 1 may have merged a newer `main` than the
  `base` line in the baseline file. For a new failure, first check whether
  `git log <baseline-base>..origin/main` touched that area. The proof that a failure
  is not yours is the failure reproducing at the current `base`, in a temporary
  detached worktree (`git worktree add --detach <dir> "$base"`) that has gone through
  the `session-init` environment step. The same proof applies when the baseline is
  unavailable. Remove that worktree afterwards.
- **Exit code first.** A killed run (for example exit 137 or 143) is "no result," not
  red. Re-run it before judging.

### 5. Commit

Use the `commit-writer` skill for the message (Conventional Commits). Stage intended
files by path. Never `git add -A` over unrelated dirty files. If a pre-commit hook is
installed and restages formatter output, confirm the staged content still matches
what the gate ran on.

### 6. Push

```bash
git push -u origin "$(git rev-parse --abbrev-ref HEAD)"
```

If a lefthook pre-push hook is installed, it runs full-tree checks that fail on the
existing baseline. Fix hook failures in files this task touched. Failures that are
only baseline debt elsewhere still block the push. Pushing with `--no-verify` needs
the user's explicit approval each time, and the PR must cite the step 4 gate
evidence for this exact head.

### 7. Create or update the PR

- **New PR.** Run `gh pr create --base main --title "<type>(scope): description"
  --body-file <file>`. Follow `.github/pull_request_template.md` (Description,
  Related Issues, Type of Change, Verification, Checklist) and add a **Review**
  section. Replace the template's Verification checkboxes (`ruff check src/`,
  `pytest tests/ -v`) with the actual evidence. Those full-tree commands do not pass
  on `main`, so ticking them would be false. Verification lists the exact gate
  commands and results, the baseline comparison, and any pre-existing static-check
  debt left in touched files. State that no CI runs tests on PRs. Keep the body to
  what a reviewer needs and do not restate the diff.
- **Draft.** Use `--draft` when the ship decision belongs to someone else, and keep
  the PR in draft while any named acceptance check (manual, UX, or local validation)
  is pending.
- **Existing PR.** The push updates it. Refresh the title and body with
  `gh pr edit` if scope changed, and add a short comment if this run did a review
  pass. Never open a second PR for the same work.
- **Linked issue.** Put `Fixes #N` in plain text, not a code span, then verify that
  GitHub parsed it: `gh pr view <n> --json closingIssuesReferences`.

### 8. Readiness and merge

Read mergeability after publishing and after every head or base change:

```bash
gh pr view <n> --json mergeable,mergeStateStatus,baseRefOid,headRefOid,isDraft
```

- `DIRTY`: repair now. Fetch, merge the latest `origin/main` SHA, re-run the gate,
  and push. The owning session does this. A coordinator never edits another
  session's worktree.
- `UNKNOWN`: GitHub has not computed mergeability yet. Re-check and do not infer a
  conflict.
- A merge that changes a reviewed area gets targeted validation or the one allowed
  focused pass. It does not reset pass counts.

Merge only when the user authorized it. Squash is the repo convention; GitHub also
allows merge commits and rebase, so choose `--squash` explicitly. Bind the merge to
the head the gate ran on:

```bash
gh pr merge <n> --squash --match-head-commit <gated-head-sha>
```

A head mismatch returns you to the gate. Do not pass `--delete-branch`. It makes
`gh` switch to `main` locally, which fails in a worktree because `main` is checked
out in the primary checkout, and the error hides that the merge already landed. If
`gh pr merge` reports any error, confirm with `gh pr view <n> --json state,mergedAt`
before retrying. `session-end` deletes the remote branch, because this repo does not
auto-delete head branches.

When merge was not authorized, stop with the exact state and the next action for
whoever owns it.

## Quick mode

Steps 4 through 8 only. Quick mode requires review evidence for the exact unchanged
diff and base: reviewer, passes, isolation, fixes and dispositions, and verdict. If
anything changed since that review, run Full mode. Quick mode never skips the gate.

## Report

```markdown
## PR prep complete
- Review: <fresh reviewer | self-review only (user-approved)>, <passes>, <verdict>; N fixed; <declined + reason | none>
- Docs: changeset <type added | none needed>; plan <updated/moved | n/a>; AGENTS.md <updated | n/a>
- Gate: static <pass | pass with pre-existing debt in X>; tests <no regressions vs baseline | ...>
- Commit: <type>(scope): subject (<short-sha>)
- PR: created | updated <url> (base <sha> / head <sha>)
- PR state: mergeable <state>; <draft | ready>; <merged at <time> | next action>
- Remaining risks: <none | list>
```

## Workflow chain

`session-init` → build → `pr-prep` → `session-end`. Standalone phases: `review`
(review only), `commit-writer` (message only), `pr` (generic PR mechanics).
