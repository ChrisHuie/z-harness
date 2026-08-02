---
name: salesagent-worktree-layout
description: "Where the real salesagent PR work lives — the skills repo is an empty stub; PRs are in sibling salesagent-<PR#> worktrees"
metadata: 
  node_type: memory
  type: project
  originSessionId: 745b1f81-2de5-41a5-8766-6e6a1442fa2d
---

<!-- audit-2026-08-01 -->
> **STALE as of 2026-08-01.** Verified no longer accurate during the memory-consolidation audit. Kept for history; do not act on it.
> Evidence: Says 'The active codebase is affinity-com/salesagent' and 'use gh -R affinity-com/salesagent'. Every one of the seven salesagent worktrees has origin https://github.com/prebid/salesagent.git, and PR #


The cwd `~/Documents/ComputedChaos/skills` is an **empty stub** (19-byte README, single "Initial commit", remote `ChrisHuie/skills`). Real work is in **sibling** directories under `~/Documents/ComputedChaos/`. The active codebase is **`affinity-com/salesagent`** (Prebid Sales Agent, AdCP protocol, Python/SQLAlchemy/pydantic), checked out across multiple worktrees named by PR:

- `salesagent/` — general checkout (was on `pr-1389-review`)
- `salesagent-1389/` — `feature/property-list-targeting` (**PR #1389**, the canonical/most-current copy)
- `salesagent-1312/` — `feature/b6-idempotency-replay-table` (PR #1312)
- `salesagent-1274/`, `salesagent-1394/`, `salesagent-pr1420/`, `salesagent-mainline/` — other PRs/branches

When the user says "this PR" while cwd is `skills`, they almost certainly mean a `salesagent-*` worktree — confirm which by recent mtime + branch name. PR # in the dir name = GitHub PR number on `affinity-com/salesagent` (use `gh -R affinity-com/salesagent`).

Repo quality bar is unusually high: CLAUDE.md treats **DRY as a correctness invariant** (pylint R0801 + ratcheting `.duplication-baseline`), there's a **mandatory pre-push full-suite gate** (`check_full_suite_before_push.py` records verified HEAD), and ~40 `tests/unit/test_architecture_*.py` guard tests. Reviews must measure against this bar, not generic standards. Related: [[pr1389-property-list-context]].
