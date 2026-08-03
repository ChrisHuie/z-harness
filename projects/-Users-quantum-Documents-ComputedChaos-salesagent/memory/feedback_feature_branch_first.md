---
name: feedback-feature-branch-first
description: "Cut feature/<slug> with --no-track as the FIRST action of implementation, before any edit. Without --no-track from origin/main, the first push resolves to refs/heads/main and GH013-rejects."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: eea6a61f-fb14-405a-8a08-b5c73900ce1c
---

(Absorbs feedback_create_branch_before_implementation + feedback_no_track_when_branching_from_origin, 2026-06-11.)

When a plan is approved and implementation begins, the first tool call — before any Read/Edit/Write — is:

```bash
git checkout -b feature/<slug> --no-track origin/main   # from local main: git checkout -b feature/<slug>
```

**Why (violated twice — treat as a hard gate):**
- "i don't see this branch?" — two edits made on main before branching.
- Issue #1246 work: "we need a new branch?? Bad oversight. Don't we have memories on this??"
- CLAUDE.md: never work directly on main. Branching retroactively hides in-flight work from `git branch` and the user's tooling.

**Why `--no-track` when basing on origin/main:** default tracking sets upstream to origin/main, so the user's later `git push -u origin feature/x` resolves the DESTINATION from the upstream's branch name → tries to update `refs/heads/main` → rejected by branch protection. Failure signature: `GH013: Repository rule violations found for refs/heads/main` with the telltale `feature/x -> main` in the push output.

**How to apply:**
- First action of implementation = cut the branch. Kebab-case, descriptive slug: `feature/cancel-media-buy`, `fix/idempotency-key-update-path`. Conventional prefixes (`feat/fix/refactor`) fine.
- From a remote base, always `--no-track`; verify with `git branch -vv` — must NOT show `[origin/main: ...]`.
- Already cut without it? `git branch --unset-upstream` BEFORE the first push.
- Already edited on main? `git checkout -b feature/<slug>` from the dirty tree (uncommitted changes follow; main stays clean) — acceptable recovery, second-best.
- Never push the branch — [[feedback_user_owns_git_push]].
