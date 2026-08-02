---
name: feedback_claimed_invariant_needs_failing_oracle
description: Every invariant a PR CLAIMS in prose needs a mechanism that goes RED when it breaks; our structural harness is blind to claimed-but-unenforced invariants
metadata: 
  node_type: memory
  type: feedback
  originSessionId: db99f216-b364-43a5-a258-cfb813c8089c
  modified: 2026-07-23T11:57:10.936Z
---

A guarantee a PR asserts in prose (PR body, docstring, comment — "errors are never cached", "single SDK seam", "the race decision has one home", "every error code is checked on the wire") is only real if some mechanism goes RED when it breaks. Four ways an invariant LOOKS enforced but is not:

1. **Docstring/convention only** — the seam/rule is described, nothing stops the next import/caller from defeating it. Fix: an AST guard ([[feedback_escalate_recurring_lessons_to_guards]] — the guard is the deliverable when AST-detectable).
2. **Unreachable defensive clause** — `if not isinstance(x, Success): return` where every caller already passes a Success. Dead code with no oracle; delete it and nothing reddens. The classic tell.
3. **Adjacent-test-green-for-the-wrong-reason** — the test that "covers" the guarantee passes because of a *neighbouring* mechanism (an early return), not the clause under review; the clause could be deleted and the test stays green.
4. **Partial enumeration** — 3 of 4 error codes asserted on the wire; the 4th verified only through the lossy reconstructed exception. Or one member of a typed family corrected (one code's recovery class) while siblings stay wrong.
5. **Centralized-helper revert masks per-site independence** — a fix consolidated into one shared chokepoint (a `reject_invalid_token()` both auth gates call). Reverting the HELPER reddens every test through every path, which LOOKS like full coverage — but proves nothing about whether each CALL SITE is independently guarded. A later contributor who re-inlines a leaking raise at one site (bypassing the helper) sails past a helper-level oracle. Fix: mutation-test each call site — inline the violation at THAT site only, confirm only its own tests redden. (#1647: inline-leak at `get_principal_from_context` alone reddened its 3 integration tests while the `resolve_identity`-routed unit + A2A tests stayed green — that is the proof, not the shared-helper revert.)

**Why:** this is the precise gap a green `make quality` + the ~50 structural guards + R0801 cannot see — every one of those checks the assertions you ENCODED, never the ones you only wrote in PROSE. A strong structural harness makes the misses cluster exactly here. (Source: the review round that found duplicated race-recovery with a substring-coupled detection, an unreachable `isinstance` cache guard, an unguarded SDK seam, and EXPIRED missing from the wire matrix — four items, one root cause.)

**How to apply:**
- For each claimed invariant, name the test/guard that fails when it breaks. If the answer is a docstring, a dead clause, an adjacent test, or "3 of 4", that is a finding.
- **Mutation-test the claim**: break the line that would violate it, confirm a test reddens. Run the mutation on DEFENSIVE clauses too, not only load-bearing logic — a clause that changes nothing when deleted is dead (remove it, or give the *real* guard an oracle and name it in a comment).
- **When a fix centralizes into a shared helper, mutation-test each CALL SITE, not just the helper** (item 5) — a single helper-level revert can't distinguish "every site guarded" from "one site guarded, the rest ride the helper by luck of routing."
- A typed-family correction (recovery class, validator, narrowing) is unfinished until swept across every sibling ([[feedback_complete_claim_requires_full_pattern_enumeration]]).
- Prefer making the invariant structurally impossible to break (one home, one seam) over testing it ([[feedback_semantic_ssot_defect_class]], [[feedback_substrate_prs_need_production_callers]], [[feedback_mock_only_tests_dont_prove_wiring]]).
