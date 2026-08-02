---
name: changed-wire-field-dormant-grader-check
description: "On a wire/protocol-field change, map the field to the conformance scenarios that grade it (even in UNtouched .feature files) and check each is actually harnessed — diff-anchored review misses a dormant grader."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: c28b1a99-2ad6-43ec-86d8-610aa5d5fe86
  modified: 2026-07-23T15:32:07.975Z
---

When a PR adds or changes a protocol/wire field, the strongest reviewers ask: *does a conformance scenario that grades this field already exist, and is it actually executing?* — then find the dormant one sitting in a `.feature` file the PR never touched.

**The miss it prevents:** the full-review dispatch is diff-anchored — `review-bdd` fires only "when the target includes `tests/bdd/`". A PR that populates a new wire field in an `_impl` + a mock unit test (no `tests/bdd/` in the diff) therefore gets NO bdd reviewer, and none of the diff-scoped specialists proactively grep the untouched `tests/bdd/features/*.feature` for a scenario that grades the new field. So "the field's grading scenario exists but is dormant (no `scenarios()` binding / no step defs / auto-xfails at the harness)" is invisible to the harness. A colleague caught exactly this by spec/domain knowledge (a mock `_impl` unit test proves model self-consistency, not wire delivery; the graded scenario was dormant in an untouched feature file).

**Why:** the harness is comprehensive on "does the diff violate a known pattern?" but diff-scoping blinds it to "a grader that SHOULD cover this change already exists elsewhere and is dormant." This is the dormancy sibling of [[bdd_inline_steps_escape_guards]] and charter gotcha #8 (auto-xfail masks pass-vs-dormant), and a [[semantic_ssot_defect_class]]-shaped gap (the concept "this field is graded" lives in an untouched file).

**How to apply:**
- On ANY protocol-response field change, run a change→grading-scenario map: `grep -rn "<field>" tests/bdd/features/` and, for each hit, check it's harnessed (bound via `scenarios()`, step defs exist, not caught by the conftest auto-xfail / a UC-specific `pytest.xfail`). Report dormant graders as a finding.
- Make `review-spec-conformance` (which DOES fire on protocol-behavior changes) OR a dedicated dispatch own this — do NOT rely on `review-bdd` being dispatched, because a field-only change won't touch `tests/bdd/`.
- Mechanized ([[escalate_to_guards]], built 2026-07-23): `.claude/rules/private/detectors/changed_field_grading_coverage.py` maps changed response fields (from the `src/core` diff, or `--fields`) → `.feature` scenarios asserting them → harnessed status (`scenarios()` binding + a step def references the field), flagging a field whose only graders are dormant (exit 1). `review-spec-conformance` OWNS running it (it fires on any `_impl`/schema change even when `review-bdd` is not dispatched); `full-review`'s dispatch note points to it. Self-test + regression corpus green (pre-fix #1677 flags, post-fix clears). It is a TRIAGE detector — a `likely-live` hit still needs the §4c-precond-2 check that the specific grading scenario is not xfailed at the harness fixture.
- Balance note: on the POST-fix re-review the harness matched/exceeded the colleague (re-derived all 4 items; ADDED an MCP structured_content `null`-leak on the degrade path, the unexercised e2e_rest dispatcher branch, a stale deletion-oracle docstring) AND caught an imprecision in the colleague's gate (it cited a `make check-dormant` target that doesn't exist). The gap is specifically the diff-anchored dispatch blindspot, not detection depth. Use [[use_full_review_skill]].
