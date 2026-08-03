---
name: feedback_cleanup_chain_use_semicolon_not_ampersand
description: Chaining a mandatory cleanup (git stash pop) after a fallible command with && silently skips the cleanup on non-zero exit
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 670a5ade-41bd-4d11-8bad-632d4b08efd3
---

When you temporarily mutate state to run a baseline/comparison — the classic case is `git stash push … && <run tests> && git stash pop` — chain the **cleanup with `;` (or a trap), never `&&`**. A test/command that exits non-zero (a bare pytest run exits 1 on failures, and even an xpass-only run can exit non-zero) breaks the `&&` chain, so the `pop` never runs and your uncommitted work stays stashed. This happened live during a PR remediation: a `&& git stash pop` after a pytest baseline left the entire uncommitted PR (10 tracked files) sitting in `stash@{0}` — recovered only by immediately checking `git stash list` + `git status`.

**Why:** it is the same exit-code-masking family as [[backgrounded_commit_exit_code_masks_failure]] — the shell's success-gated chaining hides that a required step was skipped. Losing the pop is worse than a masked test result: it silently reverts your working tree to the pre-stash (often the base/main) state, so a later "verify my changes" can read the wrong content.

**How to apply:** for any stash/mutate → run → restore dance, write `git stash push -- <files>; <run>; git stash pop` (unconditional pop), or stash only the specific files and always pop as its own separate tool call. Then VERIFY restoration (`git stash list` empty of your entry + `git status` shows your changes back) before trusting any file read. Better still, avoid stashing the working tree at all when a fallible command is in the middle — prefer a separate clean checkout/worktree for baseline comparisons ([[feedback_no_mutation_agents_on_shared_worktree]]).
