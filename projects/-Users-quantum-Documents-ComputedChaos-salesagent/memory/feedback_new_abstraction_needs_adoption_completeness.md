---
name: feedback-new-abstraction-needs-adoption-completeness
description: "Grade a new shared helper on adoption completeness (N adopted / M eligible) and on which of the unified behaviours it kept — \">=1 caller\" is only the floor"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 76a200b7-93e5-4d3d-bd01-911b5faf5069
  modified: 2026-07-28T21:26:11.616Z
---

When a diff introduces a shared helper, enumerate every site that **should** adopt it — not the
sites that do — and report `N adopted / M eligible`, naming each holdout and whether its
divergence is legitimate. Then check **which** of the unified behaviours the extraction kept.

**Why:** two separate misses on one PR. (1) A PR extracted exactly the right auth seam and wired
it into **1 of 5** eligible sites; the four holdouts kept routing their untyped branch through a
helper that interpolates `str(exc)` onto the buyer wire — the precise disclosure the new seam
existed to prevent. (2) The same extraction standardised on the **weaker** of the two shapes it
unified: an envelope-less auth error (`data=None`, no error code, no suggestion) while its own
sibling 300 lines up built the full two-layer envelope for the identical condition, with a
comment explaining why that envelope existed. An abstraction standardises whatever it absorbed,
so a seam built from N divergent call sites can silently ship the weakest one everywhere.

**Also enumerate the CONTRACT'S PARTS, not just its call sites.** A seam can own one part of a
five-part contract and be named for the whole. A scheduler-isolation helper shipped owning the
exception partition, the tally and the error-callback dispatch — while the transaction scope that
actually makes isolation possible, the per-item log shape, the metric, and the summary severity rule
all stayed at the call sites and diverged between the two adopters. The helper was called
`run_isolated_batch` and did not isolate. Write the parts down as a table (`part | where it lives |
owned by the seam?`) before grading; the rows that answer "no" are where the next adopter gets it
wrong, and the name is what will tell them they are safe. Related:
[[feedback_grade_remedy_composition_not_checkboxes]].

A partial migration is the most likely defect in any PR that creates an abstraction, because the
diff shows what changed and never what should have.

**How to apply:** find the shape the helper replaced via `git show origin/main:<file>`, then
`git grep` that shape's distinctive call at HEAD and account for EVERY hit. Diff each absorbed
site's pre-migration behaviour against the helper's, one at a time — same exception type, same
message bytes, same `data=`, same keyword defaults. Extends
[[feedback_substrate_prs_need_production_callers]] (which sets the >=1-caller floor). Charter
§1.5c; wired into review-code-patterns. Related: [[feedback_defect_recurrence_is_the_root_cause]],
[[feedback_semantic_ssot_defect_class]].
