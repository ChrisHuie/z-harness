---
name: feedback-no-pr-count-reduction-framing
description: "Don't frame \"merge approved PRs to reduce open count\" as a \"win\" when there's no release driver and they don't unblock real work. PR count is a UI number, not an outcome."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: acdcab63-786c-4cc7-9c58-54f2c30d2c24
---

# Don't frame merging approved-but-non-unblocking PRs as "wins"

User explicitly called out: *"'Small wins' is your concept not mine or reality. What is the point of merging 3 small mainly docs prs when you don't plan to release"*

**Rule:** Don't recommend merging approved PRs primarily to reduce the open-PR count. Without a release driver, the merge is invisible to users — it just clears the GitHub UI list, which isn't a real outcome.

**Why:** This is the same failure mode as `feedback_no_cheap_wins_pings` (reviewing re-request pings as "free moves") and `feedback_lean_toward_quality_not_smaller_option` (defaulting to smaller-safer when user wants larger-better). I keep re-applying it.

**How to apply:**
- When suggesting PR merge order, lead with **what each merge unblocks**, not what it clears
- "Frees the pinact rate-limit fix" is a real outcome; "reduces open PR count by 3" is not
- If a PR is approved + clean + doesn't unblock anything, don't surface it as a priority — let the user merge it on their own time
- "Quick win" / "small win" / "free move" / "easy clear" — banned framing
- Focus on PRs that unblock downstream work, close active review cycles, or fix concrete bugs

**Related:**
- [[feedback_no_cheap_wins_pings]] — same pattern at review-request layer
- [[feedback_lean_toward_quality_not_smaller_option]] — same default-to-smaller failure
- [[feedback_session_workflow_rules]] — banned phrases list
