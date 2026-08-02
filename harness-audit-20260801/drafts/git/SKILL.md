---
name: git-workflow
description: Commit, branch, stash, rebase, merge, git mv, or get a PR through GitHub CI. Use when committing or cutting a branch, when a commit or rebase may not have done what it looks like it did, when CI is not running on a PR, or before saying a change has landed.
---

# git / gh write-side mechanics

Operations that CHANGE a repo or a PR, where the command **succeeds quietly and reports the
wrong thing**. Read-only git is not here.

## Committing

- **A compound `git commit` reports the LAST stage's exit code.** `git commit …; echo; git
  log` reports `git log`'s 0 even when the commit aborted. Send a bare `git commit -q -m
  "…"` with nothing chained; confirm with `git rev-parse HEAD` (new SHA?) and `git status`
  (clean, or staged leftovers?).
- **A formatter hook that rewrites a staged file exits non-zero and ABORTS the commit.**
  Files stay staged, the rewritten one shows `MM`, HEAD never moved — this is what the
  exit-code mask hides.
- **Chain a mandatory cleanup with `;` or a `trap`, never `&&`.** A non-zero exit skips the
  `git stash pop` and the work stays stashed — a whole uncommitted PR once sat in
  `stash@{0}`. Verify restoration (`git stash list` + `git status`) *before* trusting a
  file read.
- **After `git mv`, passing the OLD path to a later `git add` fatals and aborts the ENTIRE
  add.** You ship a 100%-similarity rename with 0 insertions, losing the content migration
  and every other file in the add. `git diff --cached --stat` before committing any
  mv+edit — a real one shows a sub-100% rename. Fix: `git reset --soft HEAD~1`, add the NEW
  path, re-check `--stat`, recommit.

## Commit shape

**Land a breaking constraint and every caller and fixture fix in ONE commit.** A
type-narrowing split across commits leaves the tree red for everyone in between. Enumerate
every site it breaks first, modelling every form the matcher must catch — multi-line
parenthesized imports, aliases; `ast-grep` for call shapes. If it must split, state the push
order and that pushing the first alone breaks CI.

## Branch recovery

- Cut without `--no-track`? `git branch --unset-upstream` **before** the first push, or the
  push resolves to `refs/heads/main`. `git branch -vv` must not show `[origin/main]`.
- Already edited on main? `git checkout -b feature/<slug>` from the dirty tree — the changes
  follow, main stays clean.

## PR and CI plumbing

- **A PR at `mergeStateStatus=DIRTY` makes GitHub SKIP `pull_request` workflows** — it
  cannot build the `refs/pull/<N>/merge` commit they check out. Only `pull_request_target`
  jobs keep running, so it reads as frozen tests.
  `gh pr view <N> --json mergeable,mergeStateStatus`.
- **After every push assert BOTH**: state is not `CONFLICTING`, **and** `gh run list
  --commit <pushed-sha>` is non-empty. An empty run list for that SHA *is* the failure — the
  checks page shows the stale previous run.
- **Cherry-picking one of main's commits is how a branch goes DIRTY non-obviously.** The
  pick applies cleanly; main keeps evolving those files; the merge ref then conflicts.
  When the branch needs something from main, MERGE main — never a slice.
- **A PR runs only the workflows whose `pull_request: branches:` filter its BASE matches**,
  so one stacked on another feature branch gets no heavy CI and its CodeQL alerts stay
  frozen. A short check list there is expected, not a misconfiguration; the local full suite
  is the only gate.
- **A bot-authored PR lands `conclusion=action_required`** — required contexts never report,
  it sits `BLOCKED`, and only a human close-and-reopen clears it.
- **`workflow_dispatch` runs never attach to a PR's required contexts** — only
  `pull_request`-triggered ones satisfy the gate. A superseded check lingers beside the new
  one on the same SHA; GitHub scores the latest per context, and `mergeable` sits at
  `UNKNOWN` while it recomputes.
- **Issues and PRs share one per-repo counter and never correspond.** Confirm with `gh pr
  list --head <branch>` before citing a number; `Closes #<n>` points at the ISSUE.

## Long-lived branches

- **Check currency before writing code for a plan-grounded rebuild** — a plan written
  against a stale base is itself stale. `git fetch origin main`, then `git rev-list --count
  HEAD..origin/main` and `git diff --stat HEAD...origin/main -- <files the plan targets>`. If main already restructured them, sync and re-ground before coding. Detect
  "already synced" empirically; never wait to be told a state you can observe.
- **After merging main into a long-lived branch, sweep BOTH directions for duplicate
  helpers.** The branch hand-rolls one, main independently grows the SSOT, the merge unites
  them, and no conflict fires because the files differ. Match the idiom, not the name.
- **A rebase can resurrect the exact line a relocation PR moved.** Git keeps main's copy as
  context and the PR's as an addition, so pre-fix behaviour goes live, the PR's fix becomes
  the dead copy, its invariant comment still reading as satisfied. Count the statement per
  revision instead of reading the diff:
  `for r in <main> <pre-rebase> <post-rebase> HEAD; do echo -n "$r: "; git show "${r}:path" |
  grep -c '<stmt>'; done` — 1 → 1 → 2 is the tell. Braces are load-bearing: bare `$r:path`
  triggers zsh's `:s` modifier and git reports a bogus ambiguous argument.
