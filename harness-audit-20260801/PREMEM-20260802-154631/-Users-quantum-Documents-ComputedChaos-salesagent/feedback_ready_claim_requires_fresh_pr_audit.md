---
name: feedback-ready-claim-requires-fresh-pr-audit
description: "Any \"ready for review/handoff/clean\" claim about ANY PR requires a fresh 3-endpoint audit on THAT PR — not just the one being actively worked on"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: acdcab63-786c-4cc7-9c58-54f2c30d2c24
---

Every "ready / clean / addressed / handed off" claim about ANY PR — including PRs not currently being worked on — requires a fresh 3-endpoint audit immediately before the claim is made. Use stale conversation-summary state ONLY as a hint; the truth is on GitHub.

**Why:** PR #1276 round 8 was posted by a reviewer at 17:14Z. Last commit was at 18:18Z (after the review), but the commit message addressed a different topic — we never re-read `/reviews`. The audit memory `pr_review_audit_workflow` was being applied only to PRs under active edit; PRs being claimed "ready" via inherited compaction summary state weren't being re-checked. This let R8 sit unseen for an entire conversation about cleanup.

**How to apply:** Before any phrase like "ready for handoff", "pattern-audit clean", "we're done with #X", "addressed all feedback on #X", run this for THAT specific PR:

1. `gh api repos/<owner>/<repo>/pulls/<N>/reviews --paginate` — full review history, note the latest timestamp
2. `gh api repos/<owner>/<repo>/pulls/<N>/comments --paginate` — inline comments
3. `gh api repos/<owner>/<repo>/issues/<N>/comments --paginate` — issue-thread comments
4. Compare the latest review timestamp to our latest commit timestamp on the PR's branch — if review is newer, READ IT before claiming anything

This applies to multi-PR status reports too. When the user asks "what's outstanding across PRs?", a fresh sweep per open PR is the only correct answer. Inherited state from earlier in the conversation or from compaction summaries is allowed as a *starting* hypothesis, never as the final claim.

Related: [[pr_review_audit_workflow]] covers the discipline; this memory closes the loophole that the discipline only ran on actively-worked PRs.
