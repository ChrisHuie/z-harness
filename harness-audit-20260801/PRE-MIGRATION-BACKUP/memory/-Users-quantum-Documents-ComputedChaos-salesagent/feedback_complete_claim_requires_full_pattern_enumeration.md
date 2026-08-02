---
name: feedback-complete-claim-requires-full-pattern-enumeration
description: "Before any \"complete sweep\" or \"all addressed\" claim, enumerate EVERY known pattern across EVERY open PR — not just recent items on the current PR"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: acdcab63-786c-4cc7-9c58-54f2c30d2c24
---

Any "complete sweep" / "all addressed" / "nothing missing" claim requires:

1. **Full pattern enumeration** — the working set is **every** pattern flagged across **all** reviews, not just the latest 1-2 rounds on the current PR. Maintain a written list; re-read it each sweep. Recency bias on the pattern list narrows sweeps silently over time.

2. **Scope decisions ≠ investigation decisions.** "Path B = fix only PR X" means *don't fix* PR Y in this commit. It does NOT mean *don't check* PR Y for the same patterns. Sister PRs in a stream (#1313/#1314/#1315 trilogy) will have identical findings — verify both before scoping. Decision to defer the fix is fine; decision to stop sweeping is not.

3. **Symmetric verification of agent reports.** Agent says "violation" → verify before fixing. Agent says "clean" → verify before believing. The verification burden is the same direction. Failing to verify "clean" verdicts has burned us multiple times.

4. **Re-sweep after fixing.** `feedback_pattern_extraction` says audit other sites; that applies to the PR being fixed. THIS memory extends it: after fixing a pattern in one PR, sweep the WORKSPACE for that pattern in every other open PR. One pattern → all PRs, not one PR → all patterns.

**Why:** Repeated false "complete" claims across a single day's work. Each time, the gap was a sister PR (#1314 after #1313, R8 on #1276 we'd missed, lazy imports on #1307 sibling to #1306). The pattern-extraction discipline existed; it was being applied to the active PR only.

**How to apply:** Before any "ready" or "complete" or "addressed" claim:
- (a) Pull the explicit pattern list from past `feedback_*` memories + recent commit messages on the architecture work. Don't reconstruct from memory.
- (b) For each pattern, run `git diff main...origin/<branch>` on every open PR I authored (use `gh pr list --author "@me"`).
- (c) Spot-check 1-2 agent "clean" verdicts personally before accepting them.
- (d) Quote the evidence in the claim, not just the conclusion. "Verified X across N PRs, found Y" beats "complete sweep."

Related: [[feedback_pattern_extraction]] (single-PR site sweep), [[feedback_ready_claim_requires_fresh_pr_audit]] (re-query reviews before "ready" claim), [[pr_review_audit_workflow]] (3-endpoint base discipline).
