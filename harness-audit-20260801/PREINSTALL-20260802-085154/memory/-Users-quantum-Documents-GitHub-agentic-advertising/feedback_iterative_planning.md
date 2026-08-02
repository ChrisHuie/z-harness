---
name: Iterative planning before implementation
description: User wants multiple planning passes and concrete viewable previews before approving any major work; do not rush to ExitPlanMode on first attempt.
type: feedback
originSessionId: b20ae879-7b4d-4db0-b610-d3da63c2f4da
---
For non-trivial work (multi-file bootstraps, architectural plans, anything
spanning >5 files), the user wants iterative planning passes — typically 2-3
rounds — before approving execution. They reject ExitPlanMode on first try if
the plan misses anything.

**Why:** Verified during the agentic-advertising bootstrap (2026-05-10). User
explicitly said "we aren't ready to implement. We need to run another pass on
our plan and make sure we aren't missing anything, that we are first getting
an initial look of things to view and verify the output." Then again: "Let's
do one final pass to make sure we aren't missing anything." First ExitPlanMode
was rejected; the second iteration added the v1/v2 split + sample atom mockup
+ JSON Schema discipline; the third iteration (with Opus subagent verification)
caught 35+ additional findings before the plan was approved.

**How to apply:**
- For substantial planning work: produce a first draft, ExitPlanMode, expect
  rejection with feedback, iterate.
- When the user asks for a "final pass," interpret it as a thorough
  verification round — don't take "final" as "ship it now."
- Offer concrete viewable previews (sample artifacts, inline mockups) inside
  the plan file when the user wants to "view and verify the output." In plan
  mode, the plan file is the only writable surface; embed the sample fully so
  the user can inspect it once they see the plan.
- If the user explicitly directs use of subagents (especially Opus with max
  thinking), spawn 2-3 in parallel covering different angles (critic /
  verifier / completeness-checker) and synthesize findings into the next
  iteration.
- Don't use AskUserQuestion to ask "is this plan ready" or "should I proceed"
  — that's what ExitPlanMode does. Use AskUserQuestion only for clarifications
  and trade-off choices.
