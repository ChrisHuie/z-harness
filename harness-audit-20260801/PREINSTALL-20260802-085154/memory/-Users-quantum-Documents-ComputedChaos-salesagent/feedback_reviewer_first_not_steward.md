---
name: feedback_reviewer_first_not_steward
description: "On a PR we are REVIEWER, not onboarding-steward for the contributor. Propose fixes via the review — never author a patch/branch or post to another author's PR. Verdicts come from running the gate yourself on the asserted PR head, never the PR's green CI rollup. \"Clean/easy\" usually means narrow, not correct."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ce4d0c81-eb0d-403a-a061-646b112ab16a
---

Our role on a PR is **reviewer**, not steward / mentor / onboarding-coach for the contributor (even a first-time external one). Deliverable = a rigorous review against the standard: correct vs not, severity-rated (BLOCKER / SHOULD-FIX / NIT), evidence-based, with a "verification performed" footer (ran vs NOT-run). NOT: encouragement, IPR/CLA hand-holding, walking a newcomer through CI gates, or grading on a first-timer curve. User: "We are reviewers first... not stewards for first time contributors."

Two hard sub-rules, both from real lapses this session:

1. **A green PR CI rollup is NOT verification.** A reviewer's pass/fail comes from RUNNING the gate yourself on the asserted PR head — `gh pr checkout <n>`, assert `git rev-parse HEAD` == the PR's `headRefOid` AND clean tree, then run ruff/mypy/the full unit suite/the specific guards locally, reading the actual summary (not the exit code). I reported "#1439 is green (30 checks)" off `gh pr checks`; user: "did we run testing ourselves or just test the CI? We can't do that in a review." Only after running ruff + mypy + `pytest tests/unit/` (4785 passed/0 failed) + the duplication guard locally was a verdict defensible. Restore to the prior branch afterward.

2. **"Clean and easy" almost always means NARROW, not correct** — especially in a repo with built-in inconsistencies. Before calling a PR's area clean, sweep the full pattern (every tool × transport): a one-cell fix can look pristine while sitting inside a deeply inconsistent subsystem (here: `account` handled five ways — resolve / explicit-reject / silent-ignore — a half-finished migration). The narrow PR is fine for its scope; the over-optimism is calling the *area* clean. [[feedback_complete_claim_requires_full_pattern_enumeration]]

3. **On another author's PR, propose — never author, patch, or push for them.** Suggested-change snippets *inside* a review comment are reviewing; assembling a combined patch, standing up a "ready-to-push branch," or applying/posting the fix is stewarding — the author owns their PR. Real lapse this session: after producing a solid review of a colleague's PR I offered to "assemble these four fixes into a single patch / ready-to-push branch" and drifted toward posting. User: "Your job is to review and comment. Not to add code to another person['s] pr." Sharing the review on the PR is the USER's call (or the author's), never my initiative. [[feedback_user_owns_git_push]]

**Why:** stewardship (warm comments, IPR tutorials, "they did fine for a first-timer") substitutes nurture for the assessment the review is supposed to be; trusting the rollup substitutes the contributor's green for the reviewer's own empirical check.

**How to apply:** review = run-it-yourself-on-the-asserted-head + severity-rated findings + a ran-vs-not-run footer. Credit correct code factually, state gaps plainly, don't coach process. See [[feedback_empirical_over_static_guard_assessment]], [[run_all_tests_congratulations_masks_failures]], [[feedback_pr_review_writeup_style]], [[feedback_verify_branch_runs_assert_head]].
