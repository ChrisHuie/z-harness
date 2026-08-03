---
name: feedback-readiness-verdict-gate
description: "A 'ready/approve/meets-the-bar' verdict has hard preconditions (charter §4c) — the #1 being a FRESH review-state re-pull on the current head via review_completeness.py. A re-review that only re-checks CI + prior findings is NOT a review-state re-check. Skipping it = the documented miss."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 6dc4f05d-b0eb-4fbd-9081-6261be32a631
---

A readiness verdict is the highest-stakes thing the review suite emits, and it is **never inherited** from a prior pass. Before saying a PR is ready / meets the bar / safe to approve, ALL of charter §4c's preconditions must hold and be shown — or the verdict is "not yet / cannot confirm."

**Why:** On PR #1575 I re-reviewed a moved head, verified CI was green + mergeable + that every prior finding (mine + the maintainer's) was addressed, and said "meets the bar to approve." I never re-pulled the PR's review threads on the current head — I did a *code* re-check, not a *review-state* re-check (they are different dimensions). A maintainer then posted a review with **four** valid should-fix items on the same head, every one confirmed against the code:
- a BDD wire-oracle that was a **serializer tautology** (inline `ctx.get("wire_response")` + `model_dump()` fallback instead of the guarded `wire_dict(ctx)` helper) — I had laundered the bdd agent's honest `could-not-mutation-test` into "genuinely grades the fix";
- a **vacuity anchor applied to the BDD step but not its integration sibling** — the sibling was the exact twin of a finding *I raised and read and praised*, never swept (§1.5 / §11 failure);
- **DRY drift** in new test code (3 sites asserting 2 of 3 fields) that R0801 / the duplication baseline can't see (sub-threshold);
- a **partial-copy of the canonical status map** reproducing the #1556 defect class one set over.

His review post-dated my verdict-fetch by ~77 min, so the timing was innocent — but that is irrelevant: (a) my process pulled no comments, so it would have missed his review whenever it landed, and (b) three of the four findings were latent in the code I reviewed and I should have caught them myself.

**How to apply:** charter §4c is the checklist; the mechanized gate is
`python3 .claude/rules/private/detectors/review_completeness.py <pr> --since <your-last-review/verdict-time> --head <sha>` — run it IMMEDIATELY before any readiness verdict; exit 1 = new/unresolved reviewer feedback, so the verdict is premature. A **moved live head also exits 1** now and prints the unreviewed delta (commits + file-stat past `--head`): a readiness verdict is stamped to a head, and **a fold-in YOU requested is still an unreviewed diff once it lands** — a "trivial/test-safe" fold you flagged can quietly change a wire string, a routing branch, or a test the moment it's committed. Audit that delta; never wave it through because you asked for it. Then: mutation-test every "this test grades X" claim (never `[inferred]`); sibling-sweep every confirmed finding (grep the diff, enumerate hits — you own the twin of your OWN finding); hand-sweep new TEST code for DRY drift; check any new subset-of-a-map literal for the partial-copy class; and stamp the verdict to `(head SHA + pull time)`, never as durable "this PR is ready."

Related: [[feedback_no_ready_claims]], [[feedback_ready_claim_requires_fresh_pr_audit]], [[feedback_audit_checklist_systematic]] (Dimension A), [[feedback_no_author_filter_on_first_audit_pass]], [[feedback_pattern_extraction]], [[feedback_claimed_invariant_needs_failing_oracle]], [[feedback_review_consolidation_drops_findings]], [[feedback_escalate_recurring_lessons_to_guards]], [[reference_per_diff_review_detectors]].
