---
name: feedback-short-circuit-coverage-illusion
description: "A compound `or`/`and` guard can be fully \"covered\" while one operand is never evaluated by any test — line and branch coverage both read as covered"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 76a200b7-93e5-4d3d-bd01-911b5faf5069
  modified: 2026-07-28T21:25:56.367Z
---

For every new or changed `if A or B:` / `if A and B:` / `assert A and B`, enumerate which
operand each existing test actually **evaluates** — not which line it touches. Python
short-circuits, so a test that trips `A` never evaluates `B`: line coverage says covered,
branch coverage says covered, and `B` is dead to the entire suite. Require one test per
operand, and mutate each non-first operand away independently.

**Why:** on an A2A ownership gate, `if task is None or self._task_owners.get(id) != expected_owner:`
— the only wire test posted an *unknown* id, so `task is None` short-circuited and the
ownership compare (the actual authorization invariant) never ran on the wire at all. Deleting
`!= expected_owner` left every wire test green. Two of our reviewers had read that exact line:
the spec reviewer read it for conformance and filed a note, and nobody read it for
*testability*. A colleague found the grading consequence.

Same shape inverted in test code: `assert A and B` short-circuits on the first FALSE operand,
so a failing `A` hides whether `B` was ever checked.

**How to apply:** run `.claude/rules/private/detectors/compound_guard_operands.py --base origin/main`
— it lists every compound guard on a changed line with its operands split out. Its output is an
assignment, not a verdict: it cannot tell you which operand a test evaluates, so answer that per
guard and say "none does" when that is the answer. Charter §1.5d; wired into review-test-integrity
and review-error-wire. Related: [[feedback_claimed_invariant_needs_failing_oracle]],
[[feedback_mock_only_tests_dont_prove_wiring]].
