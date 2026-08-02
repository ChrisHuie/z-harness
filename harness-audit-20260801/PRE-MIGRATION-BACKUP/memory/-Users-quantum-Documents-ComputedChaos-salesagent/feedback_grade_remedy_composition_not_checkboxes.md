---
name: feedback_grade_remedy_composition_not_checkboxes
description: "On a re-review, grade the COMPOSITION of the landed remedies and each remedy's whole mechanism — two individually-correct fixes to one code path can compose into a worse outcome, and a remedy can fix one side of a mechanism only"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 911b3dd8-a6f2-4ab8-a7bb-b9d69b117cd7
  modified: 2026-07-28T22:39:28.871Z
---

A re-review that walks the prior ledger item-by-item and confirms each one landed at a citable line
has verified the checkboxes, not the outcome. Two things escape that pass, and both did:

**1. Remedies compose.** We filed two independent asks against the same loop: wrap each item in a
SAVEPOINT so a DB fault rolls back only that item, and re-raise the connection-error classes above
the broad catch so a real outage still trips the session breaker. Both landed exactly as written.
For the most likely failure class they cancel: the exception is re-raised *after*
`begin_nested().__exit__` has already issued `ROLLBACK TO SAVEPOINT` and recovered the transaction,
so the escape hatch throws away a working transaction and the isolation never gets to help. Proven
on real Postgres — `tx_usable_after_savepoint_rollback: True`, and continuing the loop would have
committed every sibling. Neither we nor the external reviewer noticed, because we each graded the
two items separately and the author implemented them separately.

**2. A remedy can fix one side of its own mechanism.** A reviewer asked for a `NamedTuple` because
three same-typed `str` fields were being unpacked positionally and a swap was invisible to the type
checker. The remediation introduced the `NamedTuple` and read fields by name — and still
**constructed** it positionally, so `mypy --strict` returns `Success` under a transposition and the
defect the ask existed to prevent survives. Same pattern to watch for: a docstring that documents a
hazard while the code path that would trigger it stays unguarded; a constant extracted to one home
with no test pinning its membership, so it can silently regress to three copies.

**How to apply:**
- After confirming the prior items landed, re-derive the *end state* from the code as if reviewing it cold: what happens now, per failure class, at each call site? Build the class×behaviour table.
- For every pair of prior items touching the same code path, ask what happens when both are active. Order matters — an exception handler and a context manager interact through `__exit__`.
- For every remedy, name the whole mechanism (construct **and** read; declare **and** enforce; extract **and** pin) and check each half has an oracle. Mutate the half nobody asked about.
- The composition question is invisible to a per-item ledger, so it needs its own explicit pass — put it after the ledger walk, before any readiness statement.

Charter §4c (readiness preconditions) and §12. Related:
[[feedback_claimed_invariant_needs_failing_oracle]],
[[feedback_exception_class_partition_needs_condition_mapping]],
[[feedback_verify_reviewer_fixes_against_code]], [[feedback_new_abstraction_needs_adoption_completeness]].
