---
name: feedback-infra-limitation-needs-cost-estimate
description: "The harness can't host this" is a load-bearing claim needing a prototype or line-level cost — a true premise does not license the deferral
metadata:
  type: feedback
---

Deferring a grade because the harness or environment does not support it requires either a
working throwaway prototype or a line-level cost derived from reading the actual call sites.
Never an assertion.

**Why:** we wrote "a BDD scenario cannot host this today" with a *correct* premise — the harness
built a fresh handler per dispatch, so in-memory state never survived to a second call — and
deferred to unit+integration. A colleague answered "the harness gap is the thing to close, not a
reason to defer." A later prototype graded the entire security invariant through the real gate in
~55 lines, off a ~6-line hoist. The premise was true and the conclusion was wrong.

An infra excuse is the easiest way to quietly do the opposite of
[[feedback_lean_toward_quality_not_smaller_option]], because it sounds like engineering judgement
rather than a scope reduction. Same standard as
[[feedback_claimed_invariant_needs_failing_oracle]]: a claim of impossibility needs a mechanism,
and "I could not immediately see how" is not one.

**How to apply:** before writing "cannot", spend the ten minutes on a throwaway script that tries
it. If it works, the finding is the missing primitive and the estimate is the deliverable (which
functions, roughly how many lines, what already exists). If it genuinely cannot, name the blocker
at `path:line`. Deferring is still fine on scope grounds — but then it is tracked with an owner,
and "the infrastructure doesn't support it" is not the stated reason. Charter §1.7c.
