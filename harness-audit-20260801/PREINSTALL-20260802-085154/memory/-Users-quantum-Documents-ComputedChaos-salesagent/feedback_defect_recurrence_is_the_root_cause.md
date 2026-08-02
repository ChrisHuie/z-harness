---
name: feedback-defect-recurrence-is-the-root-cause
description: "Count copies of a repeated shape BEFORE proposing a fix — N>1 means the finding is a missing abstraction, not a site defect; reporting the metric instead of the duplication is a miss"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 76a200b7-93e5-4d3d-bd01-911b5faf5069
  modified: 2026-07-28T21:25:48.585Z
---

When a defect sits inside a **repeated shape** — an auth/validation/error-handling preamble, a
setup block, a test scaffold — `git grep` the shape repo-wide and COUNT the copies **before**
writing the Fix. If N > 1 the finding is *"this operation has no home"* and the fix is the seam,
not the site.

**Why:** we reported a single-site error-collapse (one `except Exception` swallowing three
unrelated conditions) and proposed a local `except A2AError: raise`. A colleague reported the
same defect as a **missing abstraction copy-pasted six times**, which is why the new code
hand-rolled a seventh copy and drifted. Same twice over: we reported "11 mocks against a
ceiling of 10" where the finding was "one test scaffold, six copies." Both times we named the
*metric* and they named the *duplication* — and the metric framing produces a fix that leaves
the cause in place.

The structural cause is that reviewers are dispatched by DIMENSION, so a defect living on the
seam between two is owned by neither: the error-path reviewer saw a bad `except`; the DRY
reviewer owns duplication but was not looking at the auth preamble.

**How to apply:** after confirming any defect, ask "why does this exist at all?" before writing
the Fix line, and let the answer set both the severity and the remedy. This is the inverse of
[[feedback_pattern_extraction]] (which sweeps *after* a fix to find more instances) — here the
sweep comes first and changes what the fix should be. Mechanized as charter §1.5b + a
recurrence step in the code-patterns reviewer. Related: [[feedback_semantic_ssot_defect_class]],
[[feedback_new_abstraction_needs_adoption_completeness]].
