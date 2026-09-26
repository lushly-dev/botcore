---
name: session-init
description: >
  Session bootstrap for the Botcore repo: preflights the worktree, refreshes and
  records origin/main, syncs the uv environment (root extras plus editable plugin
  packages), records the pre-existing test baseline, classifies dirty files, adopts
  the provided issue or brief, and summarizes project state before work starts. First
  stage of the session loop (session-init → pr-prep → session-end). Use when starting
  a session, resuming a worktree, checking project state, or beginning implementation.
  Triggers: init, do-init, session start, bootstrap, start session, begin work, resume
  session, project state.
version: 1.0.0
triggers:
  - init
  - do-init
  - session start
  - bootstrap
  - start session
  - begin work
  - resume session
  - project state
argument-hint: "[issue number | brief]"
user-invocable: true
---

# Session Init

Bootstrap a session before doing work. Two failure classes are caught here on turn
one instead of after review:

- **Stale base.** Worktrees share one `.git`. A branch cut from an outdated local
  `main` builds on old code and can carry another task's commits.
- **Wrong code or wrong baseline.** A `pytest` or `ruff` on PATH can come from
  another environment, including one with an editable install of a sibling checkout,
  so it tests code that is not in this worktree. And `main` is not green on the full
  tree, so a failure blamed on your change may predate it.

## 1. Preflight

Establish machine state with commands, not memory:

```bash
git rev-parse --abbrev-ref HEAD    # never infer the branch from the directory name
git status --short
git log --oneline -3
git remote get-url origin
```

Stop immediately on an in-progress merge, rebase, or cherry-pick, or an unresolved
`origin`. A detached HEAD is handled below.

If the tree is dirty, classify every file as **intended task work**, **unrelated
work**, or **unknown** before proceeding. Never edit, stage, or revert unrelated or
unknown files. Record the classification for `pr-prep`.

### Detached checkouts

A worktree can start at a detached HEAD. Treat this as routine setup: create a branch
at the current commit and continue without asking. Honor an explicit user branch
name; otherwise choose a unique name prefixed by the harness (`claude/<task-slug>`,
`codex/<task-slug>`), or `<harness>/session-<unique-suffix>` when no task is known.

```bash
git switch -c "$session_branch" "$(git rev-parse HEAD)"
```

If the name already exists, pick a new suffix. Never force-create or repoint an
existing branch. Creating the branch at the current commit preserves detached commits
and dirty files. Do not reset to main or stash to attach HEAD.

## 2. Refresh the base

```bash
git fetch origin '+refs/heads/main:refs/remotes/origin/main'
base_sha=$(git rev-parse origin/main)
```

The explicit refspec proves the shared remote-tracking ref moved. A bare fetch that
only updates `FETCH_HEAD` is not freshness evidence. Retry once on a ref-lock race
from a sibling worktree. Never describe a failed fetch as fresh. Record `base_sha`,
because `origin/main` moves whenever any sibling session fetches.

Integrate by immutable SHA. Never `git pull`, never `git stash` (the stash stack is
shared by every worktree). Choose the command before running it:

- **New work, or a branch you are not resuming:** `git merge --ff-only "$base_sha"`.
  If it succeeds, continue. If it fails because the branch diverged, do not force
  it. Run the landing check in `session-end`: the branch's commits may already be
  squash-merged into main, may be another task's unlanded work, or may be genuine
  WIP. Report what you find. For new work the usual answer is a fresh branch off
  `origin/main`.
- **Resuming a branch that already carries this task's commits:** run the landing
  check first, then `git merge --no-edit "$base_sha"`. Resolve conflicts in context.

## 3. Environment

Run every Python tool through `uv run --frozen` so it resolves from this worktree's
`.venv`. Do not assume `ruff`, `pytest`, or `lefthook` are on PATH, and do not
install global packages to get them.

```bash
uv sync --frozen --all-extras --inexact
uv pip install -e "packages/botcore-llm[dev]" -e "packages/botcore-agents[dev]" \
  -e "packages/botcore-memory[dev]" -e "plugins/botcore-teams[dev]" \
  -e "botcore-connectors[dev]"
uv run --frozen python -c "import botcore, botcore_agents; print(botcore.__file__); print(botcore_agents.__file__)"
node --version
```

- `--all-extras` brings in `cdp` (Playwright) and `mcp`, which root tests import.
- `--inexact` keeps the editable plugin installs. A plain `uv sync` removes them,
  and then `tests/integration` and the plugin suites fail at collection.
- Both printed paths must sit inside this worktree. A path into another checkout is
  an environment defect to repair before any test result means anything.
- Node 20+ runs `scripts/check-*.mjs`.

Re-run this step after any base integration that changed `uv.lock` or a
`pyproject.toml`.

**Git hooks.** `lefthook.yml` defines pre-commit and pre-push hooks, but they are
only active if `lefthook install` was run for this clone. Check with
`ls "$(git rev-parse --git-path hooks)"`. Do not install lefthook globally or edit
`core.hooksPath` for the session. Hooks are not gate evidence either way, because
`pr-prep` runs the gate explicitly. Note that an installed pre-push hook runs
full-tree checks that fail on the current baseline.

## 4. Record the test baseline

Record which failures predate the session so `pr-prep` can separate regressions from
existing debt. Do this only when HEAD equals `base_sha` and `git status --porcelain`
is empty. Otherwise task changes leak into the baseline:

```bash
baseline="$(git rev-parse --git-path botcore-session/baseline.txt)"
mkdir -p "$(dirname "$baseline")"
{
  echo "base $(git rev-parse HEAD)"
  for suite in tests packages/botcore-llm/tests packages/botcore-agents/tests \
      packages/botcore-memory/tests plugins/botcore-teams/tests botcore-connectors/tests; do
    out=$(uv run --frozen pytest "$suite" -q 2>&1); code=$?
    printf '%s\n' "$out" | awk '/^(FAILED|ERROR) /{print $2}'
    echo "exit $suite $code"
  done
} > "$baseline"
```

The per-suite exit line matters: a suite that crashes before reporting (exit 2–4)
has no `FAILED` lines, and without the exit code it would look clean.

The file lives in this worktree's private git dir: it is untracked and goes away with
the worktree. On a resumed branch, keep an existing baseline file. If none exists,
report `Baseline: unavailable`, and `pr-prep` must prove each failure predates the
session.

Lint, format, portability, and file-size checks are scoped to the diff in `pr-prep`,
so they need no baseline.

## 5. Task intake

If the invocation or conversation already carries the task (issue number, brief,
plan doc), adopt it instead of asking what to build:

- For a GitHub issue: `gh issue view <number> --json title,body,labels`.
- For work tracked by a plan in `docs/features/`: read the plan. It must be updated
  in the same PR (see `pr-prep`).
- **Ask clarifying questions only for real gaps**, such as ambiguous acceptance
  criteria, an unknown owning package, or conflicting constraints. Batch them into
  one round. If nobody can answer mid-run, record the assumption durably (issue
  comment or PR body) and continue. Authorization, credentials, data safety, or an
  unresolved product decision stops the session with the blocker named.

**When the task arrives without an issue number, search for one before building.**
Search the symbol, not your summary of it (the command name, the error code, the
config key):

```bash
gh issue list --state open --search "<symbol> in:title,body"
```

An existing issue is already triaged and often names adjacent cases the new report
misses. Adopt it. If the new report is narrower, say which parts you are closing and
which you are leaving open.

## 6. Orient and report

1. `git log --oneline -10 origin/main` shows what landed recently.
2. `ls docs/features/proposed/` and the active phase in `ROADMAP.md` show what is
   queued.
3. `uv run --frozen botcore changeset-status` shows pending release notes.

```
Botcore session ready:
  Checkout: <branch> @ <short-sha> (<existing | created from detached>)
  Base:     origin/main @ <short-sha> (fresh | fetch failed, unverified)
  Tree:     clean | N files (<classification>)
  Env:      .venv synced (all extras + 5 plugin packages); imports resolve to this worktree; node <version>
  Hooks:    lefthook installed | not installed (gate runs explicitly in pr-prep)
  Baseline: N pre-existing test failures recorded | unavailable (<reason>)
  Task:     <acceptance target | "none adopted, tell me what to build">
  Finish:   pr-prep ships it; session-end closes it.
```

The report is a progress note, not a stopping point. When a task is already adopted,
continue into the work in the same turn.

## Workflow chain

`session-init` → build → `pr-prep` → `session-end`.
