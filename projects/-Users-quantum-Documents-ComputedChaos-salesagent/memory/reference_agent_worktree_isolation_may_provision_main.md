---
name: reference_agent_worktree_isolation_may_provision_main
description: "Agent tool isolation:worktree may branch from main, NOT the launching HEAD — worktree review agents must verify+self-correct the SHA"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 16074e80-a511-4c30-aeaa-f30c683e1700
---

The Agent tool's `isolation: "worktree"` does NOT reliably create the worktree at the launching session's HEAD. In a PR re-review launched from a checked-out PR head, 2 of 4 worktree agents were provisioned onto `origin/main` (the repo default/latest main commit), the other 2 onto the correct PR head — inconsistent within one fan-out. An agent that trusts its worktree would silently review `main` instead of the PR, a new false-green (findings look valid but are against the wrong tree).

**Why:** the isolation feature appears to branch from the repo's default/mainline ref (or the latest fetched main), not `git rev-parse HEAD` of the launching worktree. The primary worktree already holds the PR branch, so the agent worktree can't check out that same branch and lands elsewhere.

**How to apply:** This is exactly why charter §B ("assert HEAD == the SHA you expect before trusting any run") is load-bearing for worktree agents. When launching worktree review agents: (1) pass the explicit target SHA in the prompt, (2) instruct them to `git rev-parse --short HEAD`, and if it mismatches, `git checkout --detach <SHA>` (the established sibling-worktree pattern — do NOT `git checkout <branch>`, it's checked out in the primary worktree), review there, restore, and flag the mismatch. All 4 agents this session self-corrected correctly because the charter told them to verify first. For pure-read agents where mutation-isolation isn't needed, a shared read-only tree avoids the issue entirely. Relates to [[feedback_verify_branch_runs_assert_head]], [[feedback_reverify_pr_head_before_and_after_fanout]], [[feedback_isolate_mutation_testing_reviewers_in_worktrees]].
