---
name: feedback_evidence_is_not_a_disposition
description: A missing-test observation used as EVIDENCE inside a production finding needs its own ledger row and its own disposition — folding it in silently drops the test ask
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 911b3dd8-a6f2-4ab8-a7bb-b9d69b117cd7
  modified: 2026-07-28T22:39:41.701Z
---

When a production finding's evidence includes "and nothing tests this" / "the test injects a class
with no production pre-image", that observation is a **separate finding** about coverage. Give it
its own row and its own disposition. Folding it into the production item's evidence means the
production fix can land, the item gets ticked, and the coverage gap ships.

**Why:** we observed that a scheduler's isolation test injected a synthetic `RuntimeError` with no
production pre-image, and wrote it into the evidence for the production finding, with the ledger
marking it "folds into A1." The author fixed the production code; the test kept injecting the wrong
class. An external reviewer filed the same observation as its own ask — *"add (or convert to) a case
whose injected failure dirties the session; it will fail against the current shape, which forces the
fix"* — and got a real DB-poisoning injection. Same fact, seen at the same time; only the one with
its own disposition produced a test. Two rounds later that test's injected class turned out to be
the one the fix actually handles, while the class the issue was really about is still ungraded —
which the separate row would have surfaced immediately.

**How to apply:**
- Severity and disposition are independent (charter §3), and so are *findings*. If a sentence in your evidence would be actionable on its own, it is a finding: split it.
- Watch for these phrasings inside evidence — they are almost always their own row: "no test covers", "the injected error has no production pre-image", "the assertion would pass either way", "this is only in the PR body".
- "Folds into X" is legitimate only when the same edit closes both. If the production fix can land while the observation stays true, it does not fold.
- Corollary for consolidation: charter §4b.0 unification must preserve one row per site *and* per concern — collapsing a test gap into a code fix is the same drop as collapsing three sites into "three copies".

Charter §3, §4b.0, §4b.5. Related: [[feedback_no_optional_disposition]],
[[feedback_review_consolidation_drops_findings]], [[feedback_claimed_invariant_needs_failing_oracle]],
[[feedback_grade_remedy_composition_not_checkboxes]].
