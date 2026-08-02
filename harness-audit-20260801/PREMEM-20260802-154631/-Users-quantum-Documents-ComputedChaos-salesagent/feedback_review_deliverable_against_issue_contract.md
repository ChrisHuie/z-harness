---
name: feedback_review_deliverable_against_issue_contract
description: "Grade a fix against the issue's behavioral done-contract AND trace the changed value into downstream consumers; never post \"no blockers\" from unit/mechanism verification alone"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 72b5eab3-5772-4ea8-ac45-69eac1644028
---

A fix can be mechanically correct at the helper level yet NOT satisfy the issue's contract or be safe downstream. Two axes under-checked → posted a premature "no blockers" on a PR; user was right there were misses.

1. **Deliverable vs issue contract.** Open the issue's "Contract for done" and check EACH item — especially behavioral/storyboard ones ("both forms produce identical *downstream* output", "storyboard scenarios pass"). Helper/unit tests one layer BELOW the boundary the issue names don't count. A fix that deletes code at a boundary needs a test AT that boundary ([[feedback_mock_only_tests_dont_prove_wiring]]). `Closes #N` must not stand when contract items are unmet.

2. **Trace the changed value into its DOWNSTREAM CONSUMERS, not just its construction.** Example: `to_brand_reference` returning `None` looked "safe" at construction, but `_get_products_impl` feeds `brand → offering → brand_manifest_policy` enforcement, so `None` produced a misleading "Brand manifest required" error under `require_brand` (a real admin policy). A "safe None/default" can be misleading or wrong three calls later. Grep the field's readers.

**Why:** mechanism-correct ≠ contract-satisfied ≠ downstream-safe — three separate axes. **How to apply:** for any fix-PR review, (a) verify each issue-contract item against a test that drives the REAL entry point, (b) trace the changed value to every consumer, (c) only then rate severity. Force-push note: a reviewed commit can be force-pushed away — re-verify prior review items against current HEAD, and range-diff last-reviewed..HEAD to catch unreviewed content (but a rebase pulls in main; confirm via `gh pr diff` vs merge-base). See [[feedback_reviewer_first_not_steward]], [[feedback_trace_flows_not_claims]].
