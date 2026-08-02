---
name: feedback_mutation_oracle_selector_must_be_verified
description: "A mutation that \"reddens nothing\" is only as strong as its -k selector; prove the selector selects the scenario under test before concluding a field is ungraded."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: b4f8139b-43a8-4409-ab66-71b047289efa
  modified: 2026-07-31T14:50:06.571Z
---

A mutation oracle's negative result — "I broke the production line and no test failed, so it is ungraded" — is a claim about the **selector**, not about the code, until the selector is proven to select the grading test.

The miss: deleted a production `recovery=` kwarg and ran the BDD file with `-k "…rehydration or inv_294 or inv294…"`. Only the unit test reddened, which read as "the wire assertion was lost in a later round." The selector matched none of them: pytest-bdd derives test names from the **scenario name**, not the tag, so `@T-UC-019-inv-294-3` becomes `test_inv3_holds__typeerror_during_targeting_instantiation_…`. Re-run against the whole file: 4 failed, wire assertion intact. The false finding was one step from a public comment, and it would have contradicted a maintainer round that had explicitly asked for and verified that assertion.

**How to apply:**
- Establish the baseline count first, then mutate. `baseline N passed` → `mutated N passed` is the only trustworthy shape for "reddens nothing"; a changed *deselected* count means the selector moved.
- Before trusting a narrow `-k`, print the selected node ids and confirm the specific scenario is among them. Cheaper: drop `-k` and run the whole file.
- Charter §1.4 symmetric verification applies to mutations specifically — an empty red set is a hypothesis to falsify, and the first thing to falsify is your own matcher.
- Beware the inverse too: a spurious `1 error` under concurrent DB load looked like the mutation had an effect. Clean re-runs were identical. Re-run before attributing any delta to the mutation.

Related: [[feedback_claimed_invariant_needs_failing_oracle]], [[feedback_guard_matcher_completeness]], [[feedback_verify_before_asserting]], [[reference_bdd_harness_pitfalls]]
