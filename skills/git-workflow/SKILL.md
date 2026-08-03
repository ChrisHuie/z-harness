---
name: git-workflow
description: Running a git or gh operation that CHANGES a repo or a PR — commit, branch, stash, rebase, merge, git mv, or getting a PR through GitHub CI. Use before running one, when a commit or rebase may not have done what it looks like it did, when CI is not running on a PR, or before saying a change has landed. Not for explaining what a git command does, and not for read-only inspection.
---

# git / gh write-side mechanics

Operations that CHANGE a repo or a PR and misreport it.

## Committing

- **A compound command reports the LAST stage's exit code** — an aborted commit inside
  `git commit …; git log` reads as 0. Run the fallible op bare and verify the STATE:
  `git rev-parse HEAD` advanced, `git status` clean.
- **A hook that rewrites a staged file exits non-zero and ABORTS the commit** — files stay
  staged, the rewritten one shows `MM`, HEAD never moved.
- **A hook entry that re-resolves its own dependency lock modifies a tracked file mid-run**,
  and the framework fails any hook that does — the commit aborts citing a file you never
  touched. Pin the resolver to the lock; a later restore cannot clear it.
- **Read a hook's generator header before trusting the configured version** — a globally
  installed drop-in replacement can take over the repo's hook and install from upstream
  HEAD, ignoring the pin.
- **Chain a mandatory cleanup with `;` or a `trap`, never `&&`** — a non-zero exit skips the
  `stash pop`, the tree silently sits at base and a later read returns the wrong content.
  Better: don't mutate the tree for a comparison.
- **After `git mv`, the OLD path in a later `git add` fatals and aborts the ENTIRE add** —
  you ship a 100%-similarity rename with 0 insertions and lose every other file in the add.
  `git diff --cached --stat` any rename+edit first; a real one is sub-100%.

## Commit shape

**Splitting a breaking constraint from its caller and fixture fixes leaves the tree red in
between** — always-on carries the scope contract. Enumerate the sites it breaks first,
modelling every spelling the matcher must catch; if it must split, say the first push alone
breaks CI.

## Branches and remotes

- **Cut without `--no-track` and the first push resolves its destination from the tracked
  branch's name** — `refs/heads/main`, rejected by protection; `git branch --unset-upstream`
  before that push. Already editing on main: `git checkout -b` from the dirty tree.
- **The local default-branch ref is routinely stale** — fetch before rebasing or diffing
  against it. With a fork among the remotes the PR base is not inferable: confirm once,
  record it.
- **Verify a clone's `origin` before treating its layout as the upstream project's** — a
  diverged fork carries the same name, a different structure, and every artifact grounded on
  it inherits the error; on correction re-ground all, not just the sentence.
- **`git ls-files <dir>` before deleting under a notes or plans directory** —
  `git status` lists only the untracked ones, so `ls` overstates what is safe to remove.

## Rebase, merge, rewrite

- **Check currency before coding against a plan grounded in this branch** — fetch,
  `git rev-list --count HEAD..origin/main`, `git diff --stat HEAD...origin/main -- <the
  plan's files>`. If main restructured them the plan is stale; detect "synced" by
  observation, never by being told.
- **Merging main into a long-lived branch creates duplication neither side had** — the
  branch hand-rolled a helper, main grew the SSOT, no conflict fires because the files
  differ. Sweep both directions after each merge, matching the idiom, not the name.
- **A rebase can resurrect the exact line a relocation moved** — main's copy is context, the
  change's an addition, so both land: the fix becomes the dead copy while its comment
  still asserts it. Count the statement per revision: 1 → 1 → 2.
- **A history rewrite does not purge** — pre-rewrite commits stay fetchable by SHA until GC,
  so "we removed it" is false. Erasure needs host support, or delete-and-recreate.

## PR and CI plumbing

- **A local commit is not on a PR.** For PR-directed work, apply the scoped publication authority
  in `references/deferred.md`; before saying *pushed*, *on the PR*, or *landed*, run
  `python3 <z-harness>/tools/pr-delivery-state.py --pr <n> --repo <owner/repo>`. It must show zero
  workspace changes, local HEAD equal to PR head, and non-empty exact-head checks and workflow runs.
- **A PR at `mergeStateStatus=DIRTY` makes GitHub SKIP `pull_request` workflows** because it cannot
  build the merge ref. A stale checks page is not evidence for the new head.
- **Cherry-picking one of main's commits is how a branch goes DIRTY non-obviously** — the
  pick applies cleanly, main keeps evolving those files, the merge ref then conflicts.
  Take the whole state by merging main, never a slice.
- **A PR authored by an automation identity leaves required checks at
  `conclusion=action_required`** — they never report, it sits `BLOCKED`, and only a
  human-attributable event clears it; a `workflow_dispatch` run never attaches to a required
  context either.
**Read `references/deferred.md` first if formatters may be fighting, publication authority needs
scoping, or you are sweeping a bulk rewrite** — also the pre-commit stash cache path
and the zsh `:s` brace trap.
