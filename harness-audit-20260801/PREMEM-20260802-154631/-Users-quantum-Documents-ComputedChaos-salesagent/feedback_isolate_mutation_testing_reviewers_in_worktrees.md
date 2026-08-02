---
name: feedback_isolate_mutation_testing_reviewers_in_worktrees
description: "Reviewer agents that mutation-test (edit files then restore) must run in isolated worktrees, not a shared checkout with other agents"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: aae21ff1-43ff-448b-a554-ea0658231c89
---

When fanning out multiple review agents against one checked-out branch, any agent that MUTATION-TESTS an invariant (edit a source line → run pytest → `git checkout --`/restore) pollutes the shared working tree for every other agent reading files concurrently. In the PR #1543 fan-out, the spec-conformance and code-patterns agents both did file-edit mutation cycles on the shared worktree; the code-patterns agent got contradictory pytest results (a FAILED run reporting `delivery` content it never wrote — another agent's edit) and the spec agent saw a spurious `generation` failure on a clean tree. Both correctly detected the anomaly and re-ran (code-patterns switched to an in-memory single-process mutation script; spec re-asserted clean HEAD then mutate→restore), but it cost runs and confidence.

**Why:** concurrent readers see transient half-mutated file state; a `git status`-clean check between another agent's edit and restore still races. This is the [[feedback_no_mutation_agents_on_shared_worktree]] hazard generalized to READ agents caught in the blast radius.

**How to apply:**
- If a review fan-out includes agents likely to mutation-test (spec-conformance, test-integrity, claimed-invariant checks), either (a) launch those with `isolation: "worktree"`, or (b) instruct agents to mutation-test IN-MEMORY (monkeypatch/import-and-mutate a copy in a single process), never by editing tracked files, or (c) serialize the mutating agent after the read-only ones.
- Charter already forbids editing a shared worktree; make the brief explicit that mutation-testing = in-memory or isolated-worktree only.
Links: [[feedback_no_mutation_agents_on_shared_worktree]], [[feedback_claimed_invariant_needs_failing_oracle]], [[feedback_verify_branch_runs_assert_head]]
