---
name: feedback_findings_need_anchors_post_as_threads
description: "A finding delivered as prose in one PR-level comment has no lifecycle and gets dropped; anchor every finding to path:line and post as inline threads, and never reuse a finding ID across rounds."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: d15e20da-0c34-4049-87cf-159a68530a4b
  modified: 2026-07-29T23:10:25.283Z
---

Every review finding carries a `path:line` anchor, and outbound findings go out as **inline review threads**, not as paragraphs inside a single PR-level comment. Never reuse a finding ID (A1/B3/…) across rounds — use fresh or round-prefixed IDs.

**Why:** a thread has a lifecycle — it lands in the author's review queue, carries resolution state, and survives a push as `isOutdated`. A paragraph inside a comment has only a mention. Observed cost: a 16-item re-review delivered as one comment alongside a colleague's 9 items delivered as 9 anchored threads. The author's remediation tracked the **thread list**, and the exact items that had no thread behind them fell out — unaddressed *and* undeclined. One was additionally consumed by an ID collision: our item "A2" was remediated under the label "A3", so the real A3 silently vanished.

This is a **delivery-format** defect, not a coverage defect. Coverage was strictly broader in every round, which is why it stung — being right is not the same as being actionable.

**How to apply:** prefer `gh api repos/O/R/pulls/N/reviews` with per-comment `path`/`line` for the findings; keep a narrative PR comment for the summary, clusters, and the actions ledger. Treat an unanchored finding as a warning sign: if you cannot post it as a thread, it is the one that will be lost. Before shipping, run the disposition ledger so no severity-tagged finding lacks a resolved next action. Related: [[feedback_review_consolidation_drops_findings]] (findings dropped during synthesis — this is the sibling failure, dropped during *delivery*), [[feedback_no_optional_disposition]], [[feedback_pr_review_writeup_style]], [[feedback_readiness_verdict_gate]].
