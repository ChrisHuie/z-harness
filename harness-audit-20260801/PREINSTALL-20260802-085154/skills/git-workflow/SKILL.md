---
name: git-workflow
description: Git and gh command mechanics that fail silently - confirming a commit actually landed, cutting branches before editing, stash/pre-commit-hook interaction, `git grep -P` vs `-E`, `git mv` aborting a staged add, and mergeStateStatus causing GitHub to skip workflow runs. Use when running git or gh commands, when a git operation's result is ambiguous, when a grep came back unexpectedly empty, or before claiming anything about repository state.
---

# git / gh mechanics

Failure modes where the command **succeeds quietly and reports the wrong thing**. Each was
learned from a specific incident.

## Exit codes lie

- **Chain a mandatory cleanup with `;` or a `trap`, never `&&`.** A non-zero exit skips the
  `git stash pop` and the work silently stays stashed.
- **A backgrounded compound command reports only the LAST stage's exit code.** Never
  conclude a commit landed from the exit code of a backgrounded
  `git add … && git commit …`. Confirm with `git rev-parse HEAD` + `git status`.

## Never narrate a panic mid-operation

**Never claim files were reverted, lost, or broken while a git/hook/build operation is in
flight.** Pre-commit hooks stash unstaged changes, so a `Read` mid-run returns HEAD content
and looks like data loss. Wait for the operation to finish, read the final state, then
describe it.

Banned mid-operation: *"got reverted"*, *"edits are gone"*, *"something undid"*, *"data lost"*.
Before drafting any recovery narrative, check `ls -lt ~/.cache/pre-commit/patch*`.

## Search that returns false-empty

**`git grep -E` silently ignores `\b`** — it returns empty rather than erroring. Use `-P`.
Treat any "not found" from a subagent as a hypothesis to falsify, not a result. A
false-empty grep is how confident-wrong findings get made.

## Staging traps

- **After `git mv`, adding the OLD path fatals and aborts the ENTIRE `git add`.** Run
  `git diff --cached --stat` before committing any mv+edit change.
- **Cut `feature/<slug>` with `--no-track origin/main` as the first action of
  implementation**, before any edit. Verify with `git branch -vv`. Editing on main surfaces
  as `GH013` on `refs/heads/main` at push time — after the work is already done.

## Commit shape

**Land a breaking constraint and every caller and fixture fix in ONE commit.** A
type-narrowing change split across commits leaves the tree red for everyone in between.

Before any state claim, run `git log @{u}..HEAD` and cite the origin head. Local-only
commits make a "pushed" claim false.

## PR and CI plumbing

- **A PR at `mergeStateStatus=DIRTY` makes GitHub SKIP `pull_request` workflows.** After
  every push, assert the state is not `CONFLICTING` **and** that runs exist for the pushed
  SHA. A green-looking PR may simply not have run.
- **Issues and PRs share one per-repo counter and never correspond.** Confirm a PR number
  with `gh pr list --head <branch>` before citing it.

## Long-lived branches

- Before writing code for a plan-grounded rebuild, check the branch's divergence from
  `origin/main` **and** whether main already changed the target files. Detect "already
  synced" empirically; never wait to be told.
- After merging main into a long-lived branch, sweep **both directions** for duplicate
  helpers. On a rebase, count the moved statement per revision — note `${r}:` needs quoting
  in zsh.
