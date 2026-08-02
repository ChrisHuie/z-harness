---
name: feedback-verify-worklist-items-real
description: "When folding a reviewer's meta-pattern into a sweep, the sibling-patterns you extrapolate are HYPOTHESES, not confirmed defects. Verify each against the code before executing it. Some turn out to be non-defects (premise wrong, or the convention isn't enforced). Skipping a verified-non-defect WITH EVIDENCE is thoroughness; executing it to look list-complete churns reference files and bloats the diff."
metadata:
  node_type: memory
  type: feedback
  originSessionId: 8377e960-8e7a-4aba-8c4d-4aedb89a6629
---

A reviewer cites one site to illustrate a meta-pattern; the thorough response is to
extrapolate the sibling-patterns and fix the whole class ([[feedback_pattern_extraction]]).
But the extrapolated work-list is a list of HYPOTHESES — each must be verified as a REAL
defect against the actual code before you act on it. "Address all these patterns thoroughly"
means verify-then-fix-the-real-ones, NOT execute-every-item-to-look-complete.

**Why:** A self-built sweep work-list had 5 patterns. Two did not survive verification:
one (assert `recovery=` on every A2A envelope test) rested on a wrong premise — the
gold-standard test already asserted recovery where it mattered and the policy made it
optional; "fixing" it would have churned a reference file for zero contract gain. The
other (convert f-string loggers to %-style) was unenforced by any linter rule — pure style
churn. A third (a GAM config error "missing field=") was a subagent false positive — the
site `return`ed a degraded result, it never raised. Executing any of them would have
expanded the diff and weakened the PR while adding no value.

**How to apply:**
- For each work-list item, open the cited/sibling code and confirm the defect EXISTS
  (grep the form, read the site, check whether a linter/guard actually enforces the
  convention). Cite file:line. ([[feedback_verify_before_asserting]])
- A non-defect gets SKIPPED with one line of evidence ("13/13 already carry recovery=";
  "ruff selects no G/LOG rule"). State it in the report; do not silently drop it and do
  not silently do it.
- This is the counterweight to [[feedback_lean_toward_quality_not_smaller_option]]: lean
  toward the better END STATE, but the better end state is "every real defect fixed,"
  not "every speculative item touched." Padding ≠ thoroughness. ([[feedback_truth_over_optimism]])
- Re-verify subagent "gap" findings the same way — they carry the same confident-wrong
  bias ([[feedback_detecting_subagent_overconfidence]]); one of three completeness gaps a
  Phase-2 audit reported was a false positive caught only by reading the site.
