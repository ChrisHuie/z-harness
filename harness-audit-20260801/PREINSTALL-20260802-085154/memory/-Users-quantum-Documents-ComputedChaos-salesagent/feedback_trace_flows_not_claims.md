---
name: feedback-trace-flows-not-claims
description: "Comments, docstrings, PR descriptions, issue text, reviewer statements, and memory files are CLAIMS, not evidence. Evidence is a traced data/code flow: the call path read end-to-end, the test run, the wire observed. Ground every 'X handles Y' in the trace, not the text."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: eea6a61f-fb14-405a-8a08-b5c73900ce1c
---

(User directive, 2026-06-11: the harness must be "focused on verification|checking|tracing data or code flows over assumptions or claims in comments of the repo or in a PR.")

Text ABOUT code is a claim. Only the traced flow is evidence. The claim-sources that have concretely lied in this project:

- **Docstrings:** `_adcp_to_a2a_error`'s docstring described it as the boundary translator while admitting "currently unused by production code paths" — and a structural guard pinned it anyway, guarding dead code while the real path went unguarded ([[feedback_structural_guards_pin_production_paths]]).
- **Aspirational docstrings in substrate PRs:** "Boundary translators AND ContextManager.fail_step both call this" — zero `src/` callers existed ([[feedback_substrate_prs_need_production_callers]]).
- **Internal contract/issue items:** PR #1312 was built from a contract item instead of the spec prose and implemented the spec's INVERSE; three review rounds polished it ([[feedback_ground_protocol_work_in_spec_not_assumptions]]).
- **Tool output tails:** tox's "congratulations :)" banner over failed suites ([[run_all_tests_congratulations_masks_failures]]); a statically-"verified" tox.ini line that was never shell-executed ([[reference_tox_commands_no_shell_substitution]]).
- **Reviewer fixes:** 4 of a reviewer's literal fixes in one PR rested on false premises about dispatch paths, class defaults, or nonexistent APIs ([[feedback_verify_reviewer_fixes_against_code]]).
- **Memory itself:** this memory dir listed an `assert_envelope_shape` kwarg the live helper doesn't have, a "4 advisory sites" count that was 6, and three pre-commit traps that #1370 had already removed — caught only by the 2026-06-11 drift audit that traced each claim to current code.

**Evidence hierarchy (strongest → weakest):** observed wire bytes / run output → the test you ran → code read end-to-end along the actual call path → spec prose for the pinned version → comments, docstrings, PR/issue text, reviewer prose, memory files. Never let a lower tier overrule a higher one.

**How to apply:**
- Any "X handles Y" / "X calls Y" / "this is covered" assertion — yours or anyone's — gets grounded by tracing: grep the call sites (`git grep "name("`), read the path transport→`_impl`→repository, or run the thing. The PR description describes intent; the diff + trace is what shipped.
- Debugging: trace the DATA (what value, through which functions, serialized how per transport) rather than pattern-matching the error text to a remembered cause.
- Memory hygiene: when a big infra PR merges (pre-commit/CI/harness), drift-audit the affected memory cluster against current code — claims here decayed within days when #1370 landed.

Related: [[feedback_verify_before_asserting]] (the claim-side discipline), [[feedback_root_cause_first]] (depth bar — the trace is how you reach derivatives 2-4), [[feedback_empirical_over_static_guard_assessment]].
