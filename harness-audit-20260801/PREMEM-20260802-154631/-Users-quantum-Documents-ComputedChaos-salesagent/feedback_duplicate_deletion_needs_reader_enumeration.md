---
name: feedback-duplicate-deletion-needs-reader-enumeration
description: "Before proposing to delete one of N duplicate writes, enumerate every READER on every path including error paths. A green mutation may only mean the dependent path is untested — deleting the \"redundant\" write can silently drop a real behaviour."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 3417a11b-189e-4cd7-9455-26497192afe0
  modified: 2026-07-31T04:08:42.806Z
---

When you find the same state written twice and propose "delete the redundant
one", the deletion is a **behaviour claim**, and a green test run is not
evidence for it. Enumerate every reader of that state — on the success path AND
on every `except` path — before naming which copy to delete.

**Why:** on a review where a rebase had produced two writes of one dict key, two
independent readers (me, and a security-dimension pass) both proposed deleting
the earlier write, and one of them backed it with a mutation showing 38 tests
still green. A third pass falsified it: the earlier write was load-bearing on
exactly one path — a non-`A2AError` failure reached an `except` handler that sent
a buyer notification, and that notification read the map and returned early when
it was empty. The 38 tests were green because **nothing tested the dependent
path at all** (`git grep '_send_protocol_webhook' -- tests` → 0 hits). So the
mutation measured test coverage, not behaviour, and the "safe" deletion would
have silently stopped a buyer-facing webhook.

The generalizable trap: a duplicate write has an obvious fix and a correct fix,
and the obvious one is what a green suite endorses when the divergent consumer
is untested. Duplication findings are exactly where coverage holes hide, because
the reason the duplicate went unnoticed is usually the same reason its consumer
is ungraded.

**How to apply:**
1. `git grep -n '<the_state>' <sha> -- src` — list every read AND write, then
   classify each read by which control-flow path reaches it (success vs each
   `except`). The readers between the two writes matter, and so do the ones
   downstream of the error handlers.
2. For every reader, ask what it does when the state is ABSENT. An early-return
   on empty is the shape that turns a deletion into a silent behaviour drop.
3. Only then propose a copy to delete — and if a reader genuinely depends on the
   earlier position, the fix is to pass the value explicitly rather than to pick
   a winner between the two writes.
4. Say out loud whether your mutation run covers the dependent path. "N tests
   still pass" is a claim about the suite; pair it with the grep proving a test
   for that path exists, or state that none does.

Related: [[feedback_verify_reviewer_fixes_against_code]] (this is that rule
applied to a deletion), [[feedback_merge_creates_duplication_sweep_ssot]] (how
the duplicate usually arrives), [[feedback_claimed_invariant_needs_failing_oracle]].
