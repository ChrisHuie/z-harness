---
name: feedback_no_mutation_agents_on_shared_worktree
description: Review/verification agents that mutation-test (edit→run→revert) a SHARED worktree holding uncommitted changes can git-checkout-revert that work and feed concurrent readers transient state
metadata: 
  node_type: memory
  type: feedback
  originSessionId: db99f216-b364-43a5-a258-cfb813c8089c
---

When dispatching review/verification subagents that EMPIRICALLY mutate code (mutation testing: edit a production line → run tests → revert to confirm a test reddens), do NOT point them at a shared worktree that holds UNCOMMITTED changes. Their revert is typically `git checkout -- <file>`, which discards uncommitted changes permanently (recoverable only from the conversation transcript), and concurrent read-only reviewers see the transient mutated/HEAD state and draft spurious findings they then withdraw.

**Why:** (observed) ran 5 review agents on one worktree while it held uncommitted work — two mutators each `git checkout`-reverted a source file mid-review; three reviewers reported the tree "reverted to HEAD" / saw `# MUTATION` markers, one nearly lost an uncommitted change. The mutators DID reconstruct the files byte-identical at the end, but only because they captured the diff first — fragile, and it forced an independent tree re-verification before commit.

**How to apply:**
- COMMIT the work BEFORE dispatching mutation-testing agents (a `git checkout` revert then lands on your commit, not HEAD — nothing is lost). This is the cheapest fix and the default.
- OR give each mutating agent an isolated worktree (`isolation: "worktree"`), OR instruct empirical-verification agents to mutate a COPY (`cp` to /tmp) and never `git checkout` the shared tree.
- Independently re-verify the tree (`git diff`/`git status` + a targeted re-run) after such agents finish — never trust an agent's "restored byte-identical" claim. [[feedback_verify_before_asserting]] [[backgrounded_commit_exit_code_masks_failure]]
- Concurrent agent-db runs across reviewers also cause spurious DB errors — serialize or treat contention as noise. [[no_concurrent_agentdb_during_full_integration_run]]
- The mutation testing itself is HIGH VALUE (it empirically proves each claimed invariant has a failing oracle [[feedback_claimed_invariant_needs_failing_oracle]]) — the fix is isolation, not skipping it.
- **2nd instance (guard/self-test PR via `/full-review`):** when the review TARGET is itself a structural guard or its mutation self-test, mutation testing is the NATURAL review method, so EVERY specialist you fan out will do it concurrently on the one worktree. Even with a CLEAN committed tree (no uncommitted-work loss), one mutator's transient `_github_yaml_candidate → return False` was seen by a concurrent reviewer's `cp` backup. Telling agents "if you mutate, `git checkout --` and verify clean" is the WRONG instruction — it IS the collision path. MANDATE isolated-copy mutation up front (`git show HEAD:<file>` → scratch dir, load via importlib) in the dispatch prompt, or give each mutator `isolation: "worktree"`. The one agent that self-isolated recovered clean; the others got lucky.
