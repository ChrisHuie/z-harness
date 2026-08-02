---
name: feedback_verify_remedy_before_public_post
description: "Public artifacts (PR comments/reviews under the user's identity) must carry the CORRECT idiomatic remedy, empirically verified by running it — never the guard-convenient or agent-suggested shortcut; destructive fixes (delete/revert/discard work) are a red flag to find the non-destructive alternative first."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 5ac79e3e-cdeb-4271-afe6-fd6fa6b3f237
---

I posted a PR review recommending a contributor DELETE their new test file to clear a DRY-duplication guard. The user rejected it ("should we really be recommending deleting a file?"), deleted the posted comment, and said "be better before we post next."

**Why:** Deleting contradicted the project's own DRY remedy ([[CLAUDE.md]]: "extract a shared helper function," never "delete one of the duplicates"). The correct fix was to extract the shared scaffold into the existing test-helpers module and KEEP the file (a distinct, legitimate regression test). I anchored on the delete-and-fold path because it was CONVENIENT for passing the guard, not because it was correct — and I posted it despite having flagged steps as not-yet-run, and despite having propagated subagent claims (one unverified: a helper path that didn't exist; one outright wrong: `AnyUrl == str`). Convenient ≠ correct, and "directionally right with caveats" is below the bar for a public artifact.

**How to apply:**
- The bar for public artifacts (PR comments/reviews posted under the user's identity) is HIGHER than chat. Before posting, the recommendation must be (a) the genuinely-correct, idiomatic remedy derived from root cause + the project's stated principles, and (b) empirically VERIFIED by running it — not asserted, not "should work."
- A destructive remedy (delete a file, revert, discard someone's work) is a RED FLAG: first find the non-destructive alternative (extract/refactor/rename). Deleting to satisfy a guard is almost never the right default.
- Don't launder subagent output into a recommendation — re-verify every load-bearing agent claim against current code/by running it BEFORE it shapes anything public ([[feedback_detecting_subagent_overconfidence]]).
- Relates to [[feedback_user_owns_git_push]] (the confirm-before-posting mechanics), [[feedback_verify_before_asserting]], [[feedback_no_ready_claims]], [[feedback_empirical_over_static_guard_assessment]], [[feedback_lean_toward_quality_not_smaller_option]].
