---
name: feedback-no-author-filter-on-first-audit-pass
description: "When pulling PR review activity, NEVER filter by author on the first pass. Always inventory ALL commenters first, then narrow. Author-filter-first creates blind spots — if a different reviewer (not the cited one) drops a strategically important comment, it's invisible."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: acdcab63-786c-4cc7-9c58-54f2c30d2c24
---

User feedback (PR #1312 audit, 2026-05-25):
> "what is wrong with you? You don't look for comments on prs? Come on bro"

I hit all 3 GitHub endpoints (`/reviews`, `/comments`, `/issues/comments`) but added `select(.user.login=="<one_reviewer>")` to every query because I was tunneled on one reviewer's review. A separate reviewer had posted a strategically important comment that was invisible to me until the user prompted me to look again.

**The overlooked comment was:** "gentle reminder that you get this for free in python sdk 4.4+" — meaning the entire custom implementation in #1312 may be redundant if we upgrade. Strategic implication, not a nit.

**The mistake:** filtering by author BEFORE inventorying who's commenting. If I'm thinking "one reviewer's review," I miss everything from anyone else.

**The corrected workflow:**

1. **First pass: list ALL commenters and timestamps, no author filter.**
   ```bash
   (
     gh api repos/<owner>/<repo>/pulls/<n>/reviews --jq '.[] | "REVIEW \(.submitted_at) @\(.user.login) [\(.state)]"'
     gh api "repos/<owner>/<repo>/pulls/<n>/comments?per_page=100" --jq '.[] | "INLINE \(.created_at) @\(.user.login)"'
     gh api "repos/<owner>/<repo>/issues/<n>/comments?per_page=100" --jq '.[] | "PR-COMMENT \(.created_at) @\(.user.login)"'
   ) | sort
   ```

2. **Read the author list.** If multiple distinct authors are commenting, treat the PR as a multi-reviewer thread. Pull the FULL body of every recent comment, not just the cited reviewer's.

3. **Only narrow by author once you know everyone in the conversation.**

**Specifically prohibited as a first-pass query:**
- `select(.user.login=="<one_name>")` on any endpoint when the goal is "what's the current review state"
- Asking "what did <reviewer> say?" without first asking "who's commenting?"

**Why this matters specifically for salesagent:**
- The PR review process here includes external reviewers (Scope3 maintainers, AdCP working group members)
- A non-codeowner can drop strategically important context (e.g., "this is in the SDK now")
- Missing those comments creates avoidable rework

**Related:** [[pr_review_audit_workflow]] — captures the 3-endpoint mechanic; this memory is the must-not-do that pairs with it.
