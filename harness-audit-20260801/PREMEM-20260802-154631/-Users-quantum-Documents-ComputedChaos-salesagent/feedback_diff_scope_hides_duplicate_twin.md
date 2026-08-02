---
name: feedback_diff_scope_hides_duplicate_twin
description: "A newly-added symbol may duplicate a canonical one in an UNTOUCHED file; diff-scoped review can't see the twin — grep repo-wide for every new symbol."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7a08ce1d-8929-4504-b06a-874a61ab2cb9
---

The costliest duplication in a PR is a NEW symbol (helper, function, translator, test util) that re-implements a canonical one whose definition lives in a file the diff does NOT touch. A reviewer reading only the diff has no way to know the twin exists — and neither does a diff-scoped agent. The clone/duplication baseline also misses it when the bodies differ below the textual-clone threshold (different patches, identity construction, args). Exemplar shape: a new test helper re-implemented a canonical wire helper whose own docstring literally said "single source of truth"; every review pass missed it, a colleague raised it a day later.

**Why:** "is this new?" and "does an equivalent already exist?" are repo-wide questions, not diff-local ones. Confining the search to the diff answers a different, narrower question and reads as "clean" when it isn't. This is the same failure family as [[feedback_semantic_ssot_defect_class]] (one concept in N places, invisible to guards) and [[feedback_merge_creates_duplication_sweep_ssot]], but the specific enabler here is diff-scoping, not guard-blindness.

**How to apply:** for every NEW top-level `def`/`class`/constant in a diff, `git grep -nE "def <name>\b" src/ tests/` (or the equivalent) repo-wide BEFORE treating it as new. Run `.claude/rules/private/detectors/ssot_docstring_duplication.py --base origin/main` — SSOT-CONTRADICTED = a "single source of truth"/"canonical" docstring whose symbol is defined in ≥2 files; SSOT-CLAIMS-TO-VERIFY = canonical claims to trace by hand for a differently-named SHAPE twin. Generalizes past duplication: any "is X already handled elsewhere?" check must leave the diff. See [[reference_per_diff_review_detectors]], [[feedback_pattern_extraction]].
