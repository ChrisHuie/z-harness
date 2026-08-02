---
name: feedback_prior_round_finding_needs_remeasure
description: "A finding from our own earlier review round is a lead, not a fact — re-measure counts and mechanisms before re-quoting them"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: b9324151-908f-41b4-9a0b-cdecca3d8647
  modified: 2026-07-31T11:57:46.461Z
---

A quantitative or causal finding **we** produced in review round N must be re-derived on the current tree before it appears in round N+1's artifact. If it cannot be re-derived, downgrade it to `[inferred]` or drop it.

**Why:** [[verify_before_asserting]] disciplines memory and [[trace_flows_not_claims]] disciplines other people's prose, but nothing disciplined our own review corpus — so a measured-once number gets quoted as established and hardens instead of dying. Two instances in a single session: (a) a replacement paragraph we proposed for a PR's spec-grounding note asserted a storyboard ratio and an absolute "no run ever holds X"; the author adopted it verbatim and a later pass over the full compliance tree found the ratio did not reproduce at any scoping and produced a named counter-example. (b) a round-2 finding attributed a `caplog` failure to a `basicConfig(force=True)` call; the next round promoted that to "the proven mechanism" in a draft, and a probe showed that function's only caller is a startup path pytest never invokes. Both were our sentences, re-asserted without re-running. The cost is asymmetric: our wrong finding lands in someone else's PR and is then defended by our own prior authority.

**How to apply:** when carrying an item forward, tag every number and every "because X" in it as needing a fresh command. Re-run it, or say plainly that it is unverified this round. Applies hardest to text we proposed that an author has already adopted — that is the case where nobody else will check it. Encoded as review-charter §1.5b's sibling rule §1.1b. Related: [[verify_reviewer_fixes]], [[subagent_mechanism_is_a_claim]].
