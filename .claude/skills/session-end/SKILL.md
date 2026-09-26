---
name: session-end
description: >
  Close out a Botcore session so it can be archived without losing work: verify
  every PR landed (by content, not commit identity), file issues for findings raised
  but never tracked, capture durable knowledge into skills, docs, or memory, delete
  merged remote branches last, and emit an archive-readiness report. `check` audits
  read-only; `park` pauses unfinished work with a resume pointer. Third stage of the
  session loop (session-init → pr-prep → session-end). Use when ending, closing out,
  or wrapping up a session, or asking whether a session is safe to archive. Triggers:
  end session, do-end-session, close out, wrap up, session done, ready to archive,
  park session, did it land.
version: 1.0.0
triggers:
  - end session
  - do-end-session
  - close out
  - wrap up
  - session done
  - ready to archive
  - park session
  - did it land
argument-hint: "check | park"
user-invocable: true
---

# Session End

Closes the loop `session-init` opened. The goal: nothing durable exists only in this
session's transcript, and nothing unlanded is silently lost when the worktree is
reclaimed.

## Modes

| Argument | Mode | What runs |
|---|---|---|
| `check` | **Audit** | Phase 1 only. No issue creation, doc edits, or branch deletion; the only write is fetching `origin/main`. |
| _(none)_ | **Full** | Audit → land → capture → verify → clean up → report. |
| `park` | **Park** | Audit → capture → report with an explicit resume pointer. |

**Ordering is the safety property.** Cleanup comes last because an earlier phase may
still need the branch. Never remove the local branch or the worktree itself. The
harness owns those.

## The landing check

By convention, PRs here land as **squash merges**. Squashing destroys every identity
handle: commit SHAs, patch-ids, and branch refs. To answer "did my work land on
main?", compare content:

```bash
git fetch origin '+refs/heads/main:refs/remotes/origin/main'
git diff origin/main HEAD -- <files this session changed>
```

An empty diff means landed. A non-empty diff means not landed, or main moved past
you. Read the diff to tell which. Never answer the question with:

- `git rev-list origin/main..HEAD` or `git cherry`. After a squash, "N commits ahead"
  looks the same whether the work never started or already landed.
- The remote branch's presence or absence. This repo does not auto-delete head
  branches, so a surviving branch says nothing about merge state. Read the PR.

## 1. Audit

Machine state, from commands:

```bash
branch=$(git rev-parse --abbrev-ref HEAD)
git status --short
if git rev-parse -q --verify "refs/remotes/origin/$branch" >/dev/null; then
  git log --oneline "origin/$branch..HEAD"               # unpushed commits
else
  echo "branch never pushed (or remote ref pruned): all local commits are unpushed"
fi
gh pr list --state all --head "$branch" --json number,state,headRefName,url \
  --jq ".[] | select(.headRefName == \"$branch\")"        # the select is load-bearing
```

For each PR, `gh pr view <n> --json state,mergedAt` separates `MERGED` from
`CLOSED`. For any ambiguity, the landing check above is authoritative.

Then do the part no script can: **sweep this session's conversation** for problems
raised but never fixed, filed, or carried by a PR. That includes deferred review
findings, flaky or baseline-failing tests you noticed, surprising behavior, and "we
should probably…" asides. List them before touching anything.

## 2. Land the work

Every session PR ends up merged, or closed with a recorded reason.

- **Check for supersession before waiting.** A parallel session may have landed an
  equivalent change. Close redundant PRs as superseded rather than babysitting them.
- If the PR needs changes or goes `DIRTY`, fix it through `pr-prep`, which owns
  gate, push, and PR updates.
- Merging needs the user's authorization. Without it, report the PR as the open
  follow-up.
- If waiting would block the close-out indefinitely, switch to `park` with a resume
  pointer.

`park` means the owner has stopped, not just that work is unfinished. Stop this
session's own background waits or child processes before reporting parked. Never
stop another session's processes. A draft awaiting human validation can close out
as not ready, naming the exact PR, the validation owner, and the check.

## 3. Capture

- **Untracked findings become issues or an explicit decline.** Findings worth acting
  on become GitHub issues (`gh issue create`). "Not worth tracking" is a recorded
  verdict, not a skipped step. Do not leave findings only in chat.
- **Durable knowledge goes to its owner.** Repo conventions go in the owning skill:
  project-only skills in `.claude/skills/` (no `source:` field), or bundled skills in
  `src/botcore/skills/`, which ship and need a changeset. Commands and structure go
  in `AGENTS.md`. Cross-session facts that are not in the repo go to memory. Capture
  only what a future session cannot cheaply re-derive.
- **Close the task.** Verify that the PR moved the `docs/features/` plan and updated
  `ROADMAP.md`, rather than assuming it did. Close or comment on the claimed issue.
- Repository edits made during close-out ship through a new PR via `pr-prep`. Never
  push doc edits onto an already-merged branch.

## 4. Verify nothing is left behind

Re-check: clean tree, no unpushed commits, no open session PRs, and the landing
check empty for every file the session changed. Unverifiable state blocks the same
way known-unpushed work does. "Could not check" is not "nothing to lose."

## 5. Clean up: last, and confirmed

Only after every PR is merged (verified by content) or explicitly abandoned. Head
branches survive merge here, so a merged session branch normally still exists on
`origin`. Confirm with the user, then:

```bash
git push origin --delete <branch>
```

`remote ref does not exist` means someone already deleted it, which is the desired
end state. If nobody is available to confirm, report
`Remote branches: retained (awaiting delete confirmation)` and list the branch under
**Follow-ups**. Never delete `main` or any branch whose content has not landed.

## The close-out report

End every mode with exactly this layout. The status is the literal last line:

```markdown
## Session close: <session title>

- Verified at: <UTC timestamp of the final PR/branch re-read>
- Pull requests: #N merged | #N closed (<reason>) | #N open (<next action>) | none
- Landing check: empty for all changed files | <files not landed>
- Issues filed: #N <title> | none
- Knowledge captured: <skill/doc/memory touched> | none
- Task/plan: <issue closed / plan moved / n/a>
- Remote branches: <deleted | already gone | retained (why)>
- Left behind: <knowingly-not-done items needing nothing from the reader> | none

**Follow-ups:** <numbered items needing the user's action> | none

**Ready to archive** | **Not ready to archive: <specific reason>** | **Not ready to archive: parked, resume at <next action>**
```

Every row is always present. Write `none` or `n/a` rather than omitting a row,
because a missing row reads as unchecked. PR state is volatile: take the final read
after the last piece of work, immediately before composing the report, and stamp
`Verified at` from that read. When you cannot re-read, report the action ("pushed
at 14:02Z"), not the state ("PR is ready"). Only claims about state go stale.

## Workflow chain

`session-init` → build → `pr-prep` → `session-end`. Use `check` at any time to ask
"is this session safe to archive?" without changing anything.
