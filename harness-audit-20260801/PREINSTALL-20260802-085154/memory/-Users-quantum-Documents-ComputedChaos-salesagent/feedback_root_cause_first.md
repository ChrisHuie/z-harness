---
name: feedback-root-cause-first
description: "The depth bar: attain the highest level of understanding through verification/testing BEFORE proposing or claiming — trace technical relationships to the 2nd/3rd/4th derivative. Bar set by the gold-standard PRs (#1306/#1307/#1312/#1389)."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: eea6a61f-fb14-405a-8a08-b5c73900ce1c
---

Always analyze issues in the project's full architecture context before proposing fixes; never jump to surface patches. Raised from "root cause first" to an explicit DEPTH BAR (user, 2026-06-11): consistently attain the highest level of understanding through verification and testing, understanding technical relationships and interactions at the 2nd/3rd/4th derivative level — the standard the gold-standard PRs were held to.

**The derivative levels — what "understood" means before proposing or claiming:**

1. **1st — the change itself.** The exact behavior at the cited line and the full execution path (transport → _impl → repository → DB). Is the issue a test-level problem, a missing architectural constraint, or a design gap?
2. **2nd — its interactions.** Everything the change touches across boundaries: all three transports (MCP/A2A/REST serialize differently — [[reference_mcp_structured_content_bypasses_model_dump]]), guards and allowlists, fixtures/factories, and every sibling site of the same pattern ([[feedback_pattern_extraction]]).
3. **3rd — what masks or proves those interactions.** Does the test prove the code or the mock ([[feedback_mock_only_tests_dont_prove_wiring]])? Is the green real or a masking gotcha ([[run_all_tests_congratulations_masks_failures]])? Is the behavior grounded in the spec, not the SDK or assumption ([[reference_adcp_spec_grounding]] — PR #1312 built the spec's INVERSE and three review rounds missed it)?
4. **4th — what keeps it true.** Which guard/gate/contract enforces the behavior after this session ends ([[feedback_escalate_recurring_lessons_to_guards]])? Honest capability declaration over silent degradation (PR #1389: compile `property_list` to native targeting or raise UNSUPPORTED_FEATURE with field+suggestion — never silently drop).

**Provenance of the bar:** #1306/#1307 (error-emission architecture: cross-transport normalization parity, boundary-never-raises), #1312 (the spec-grounding failure mode), #1389 (honest-declaration boundary). Each landed only after verification at all four levels; each earlier shortfall was a level skipped.

**How to apply:** Before any fix proposal or "addressed" claim, walk the four levels explicitly — a proposal grounded only at level 1 is a surface patch, the thing this memory exists to prevent. The instruments are empirical: run the real wire per transport, run the suite ([[feedback_run_full_suite_before_every_push]]), and check that enforcement exists, rather than reasoning from the diff.

Related: [[feedback_truth_over_optimism]] (the posture), [[feedback_verify_before_asserting]] (claim discipline), [[feedback_thorough_review]] (verification rounds).
