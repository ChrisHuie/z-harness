---
name: feedback-flaky-test-single-green-run-is-luck
description: "A single green CI/e2e run on a timing-sensitive test (especially strict=True xfail) is NOT proof of reliability — run it N times before any 'solid/ready/gold-standard' claim. And verify the ACTUAL shipped artifact, not a reconstructed or older variant."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 43053163-b525-4782-b285-ca493d76066b
---

A single green CI or local e2e run on a timing-sensitive test proves nothing about reliability. Flaky tests pass *most* of the time — "all checks green" can be the lucky branch of a race.

**Two ways this bit me on prebid/salesagent #1465 (both produced confidently-wrong calls):**

1. **"BLOCKER-2 refuted — 5/5 xfail."** I ran the reconstructed `blocker2-test` tree, which carried the *older* delivery-test version (bare `clear()` + inline localhost fixture), not the colleague's *shipped* drain-based version. 5/5 xfail on the wrong artifact said nothing about the real one. **Always run the exact shipped file/commit, never a reconstruction or an older variant of it.** [[feedback_verify_branch_runs_assert_head]]

2. **"All 31 checks green → gold-standard handoff."** The E2E check had passed once — by luck. The `strict=True` xfail `test_update_media_buy_push_webhook_delivery` actually xpassed **~1/3 of runs** (2/6, then confirmed by an 8× sweep). A flaky strict-xfail reddens CI intermittently; one green CI run is not a green test.

**Mechanism worth remembering (generalizes):** `create_media_buy` delivered its completion webhook **twice** (same `sequence #1`), and the test's drain `clear()`d only the first — the duplicate leaked into the update window and falsely satisfied the strict-xfail's assertion → intermittent XPASS. Fix was a **drain-to-quiescence** (clear until a quiet window passes), verified 8/8 xfail. Duplicate/late async deliveries leaking past a single `clear()` is a recurring webhook-test trap.

**Rule:** before calling any timing/async/strict-xfail test "solid" (and before a "gold-standard handoff" — [[feedback_pr_review_writeup_style]], [[feedback_no_ready_claims]]), run it **N times** (≥5, more if the suspected flake rate is low) on the real artifact and require 0 unexpected outcomes. Treat a strict-xfail as a load-bearing assertion: it must FAIL *reliably*, not usually. See also [[run_all_tests_congratulations_masks_failures]], [[no_concurrent_agentdb_during_full_integration_run]].
