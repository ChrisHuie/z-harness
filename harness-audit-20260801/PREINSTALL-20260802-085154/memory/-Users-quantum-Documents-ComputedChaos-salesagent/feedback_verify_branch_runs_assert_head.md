---
name: feedback_verify_branch_runs_assert_head
description: Per-branch make-quality verification MUST assert HEAD==expected SHA + clean tree; make quality dirties .duplication-baseline which silently blocks checkouts
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 8377e960-8e7a-4aba-8c4d-4aedb89a6629
---

When verifying multiple branches by checking out each and running `make quality`, a `git checkout <branch>` can **silently fail** and leave you on the previous branch — so the run executes on the WRONG tree and reports a false result. This caused a real incident: a branch failing the Pattern A guard was reported "clean" because the verification ran on a different branch's tree.

**Root cause:** `make quality` runs the duplication check which **modifies `.duplication-baseline`** (auto-ratchets it down). That leaves the working tree dirty. A subsequent `git checkout <other-branch>` then fails (the dirty file conflicts with the target branch's version) — and if you suppress errors with `>/dev/null 2>&1`, the failure is invisible. HEAD stays put; the next `make quality` runs on the stale tree.

**How to apply — every per-branch verification run must:**
1. `git checkout -- .duplication-baseline` (discard the make-quality dirt) BEFORE switching.
2. `git checkout <branch>`.
3. **Assert** `git rev-parse --short HEAD` == the expected commit SHA, and `git status --porcelain` is empty. Print MATCH/MISMATCH; ABORT the run on mismatch. Do NOT trust a run whose HEAD you didn't assert.
4. Run `make quality`, redirect to a file, capture EXIT via `set -o pipefail`, and grep the FULL output for `FAILED` (excluding `xfail`) — never trust a tail or the background-task "exit code 0" (that's the pipe's exit, not make's).

Symptom that exposes a wrong-tree run: identical test COUNTS across "different" branches (e.g. several branches all reporting "4713 passed" means they ran on the same tree). Real per-branch counts differ.

Ties to [[feedback_truth_over_optimism]] and [[feedback_no_ready_claims]]: a green result is only trustworthy if you verified it ran on the intended commit with a clean tree.
