---
name: feedback-guard-matcher-completeness
description: "A structural guard only catches the syntactic forms its matcher models. An empty allowlist reads as 'every site caught' — but if the matcher misses an equivalent form (e.g. models `X is None` but not `if not X:`), the anti-pattern survives in the very files you migrated, with false confidence. When writing/escalating a guard, enumerate ALL equivalent forms and add a positive+negative detector self-test."
metadata:
  node_type: memory
  type: feedback
  originSessionId: 8377e960-8e7a-4aba-8c4d-4aedb89a6629
---

Escalating a recurring lesson to a structural guard ([[feedback_escalate_recurring_lessons_to_guards]],
[[feedback_pattern_extraction]]) only works if the guard's matcher is COMPLETE. The
guard's empty allowlist + green run reads as "every business-logic site is caught" —
but the guard only flags what its AST matcher models. A matcher that handles one form
and silently ignores an equivalent one gives FALSE assurance, and the anti-pattern
survives — often in the exact files you just migrated.

**Why:** A `no-handrolled-identity-guard` modeled `X is None` (ast.Compare/Is) and
`assert identity is not None`, migrated its sites to green, and was committed as "done."
A Phase-2 audit ([[feedback_two_phase_subagent_audit]]) then found `if not principal_id:
raise ...` (ast.UnaryOp/Not) — the truthiness-equivalent form — sitting THREE LINES from
a migrated assert in the same function. `not X` is exactly `X is None`/`is falsy` for these
guards, but the matcher never modeled it, so the empty allowlist lied.

**How to apply — when writing or extending an AST/structural guard:**
1. Enumerate every syntactically-distinct way to express the anti-pattern before coding
   the matcher: `X is None`, `not X`, `X == None`, `not X.attr`, `if not X.is_authenticated`,
   or-chains of each. Model all of them (or document precisely which shapes are out of scope
   in the guard docstring — do NOT let the docstring overclaim "every guard").
2. Add a detector self-test with a POSITIVE case (the pattern → flagged) AND a NEGATIVE case
   (a legitimate look-alike → not flagged). A guard that trivially returns 0 because its
   matcher matches nothing is worse than no guard.
3. Treat an "empty allowlist" claim as a hypothesis to falsify, not a proof. Grep the tree
   for the prose form of the anti-pattern and reconcile against what the matcher found.
