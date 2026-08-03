---
name: feedback-no-cheap-wins-pings
description: "Drop the \"cheap wins\" framing for posting re-review-request comments on a PR. Pings don't change underlying review state — they add to the reviewer's notification noise without buying anything actionable. Don't recommend them as easy/free moves."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: acdcab63-786c-4cc7-9c58-54f2c30d2c24
---

Stop framing re-review-request comments to a reviewer as "cheap wins" or "high-leverage zero-cost moves." They are neither. Pinging doesn't change the review state — it just adds notification clutter to a queue the reviewer is already balancing. If a PR is addressed and waiting, it's waiting whether or not we ping. Pinging doesn't accelerate the review.

**Why:** User explicitly called this out ("Pinging isn't a cheap win? Get rid of that dumb ass idea"). The framing implies low-cost-high-return, but the actual return is near-zero. Even worse, framing it as a "win" cargo-cult-encourages over-pinging, which is the exact respect-the-reviewer anti-pattern.

**How to apply:**
- Never call posting a re-review-request comment a "cheap win," "free move," "high-leverage," or any framing that implies it changes outcome.
- If a comment was drafted earlier and the user hasn't posted it, mention it once as a deliverable they can post when they choose. Don't re-suggest it as a "should-do."
- When recommending what to focus on next, exclude "ping waiting PRs" from the menu unless the user specifically asks "what can I post." Posting is the user's call, not a recommendation.
- "Wait for the reviewer" is itself a legitimate answer — name it directly instead of dressing it up as activity.
