---
name: feedback-snowball-to-avalanche
description: "Momentum is OK; skipping the full suite is OK ONCE. After the first CI surprise (something broke that the targeted run didn't catch), the next push must hit the full suite — the skip is no longer a shortcut, it's compounding."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: acdcab63-786c-4cc7-9c58-54f2c30d2c24
---

User framing (PR #1306, session of 2026-05-25): "We can be momentum focused... Just remember when a snowball gets big enough rolling down a hill it becomes an avalanche."

**The shape:**
- Momentum is valuable. Targeted-test-only commits are often fine and ship faster.
- The failure mode isn't skipping the full suite — it's skipping it AFTER a skip already burned us in this PR / session.
- One CI surprise = the snowball is rolling. Two without a course correction = avalanche.

**Concrete recognition signals (this session's actual pattern):**
- Commit B (PR #1306): ran targeted tests, pushed, CI surfaced `Integration (infra)` failure I missed → 1 surprise
- Commit C: ran targeted + unit suite (NOT integration), pushed, CI surfaced 11 more failures across 3 different test files → avalanche
- The second skip after the first surprise is the failure pattern, not skipping in general

**Rule:**
- One skip is fine. After the first "CI caught what local didn't" event in a session, the next push MUST include full integration + e2e suite output. No exceptions until the avalanche has been arrested.
- Track skips in working memory across the session, not just the current commit.
- "Targeted passed" claims after a surprise are no longer enough — the contract escalates.

**How to apply:**
- Before push, ask: "Has any CI surprise already happened in this PR's history?" If yes, full suite is the next push's gate.
- If skipping is tempting after a recent surprise, that's the avalanche tell — run it anyway.
- The penalty for one wasted full-suite run is small (~10 min). The penalty for back-to-back surprises is rebuilding reviewer trust.

Related: [[feedback_run_full_suite_before_every_push]] (the standing rule); this memory adds the escalation signal.
