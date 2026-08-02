---
name: feedback-escalate-recurring-lessons-to-guards
description: "Memory is the WEAKEST behavioral lever — recall ≠ enforcement; rules get cited AFTER being violated, not before acting. A lesson violated more than once must be ESCALATED to a mechanical gate, not restated. Leverage hierarchy: soft memory < turn instruction < CLAUDE.md < structural guard / pre-commit that FAILS."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 8377e960-8e7a-4aba-8c4d-4aedb89a6629
---

When a documented lesson keeps getting violated, adding more memory text does
not fix it — the lesson was already in memory and still didn't fire at the
decision point. I cite the rule AFTER shipping the violation, not before acting.

**Why:** [[feedback_pattern_extraction]] was detailed and correct and STILL got
violated (a helper extraction migrated one function and left a byte-identical
sibling in the same file). The rule existing changed nothing. The only durable
fix is to remove the discretion.

**Leverage hierarchy (weakest → strongest):**
1. Soft memory — discretionary; depends on me applying it at the right moment
2. An explicit instruction in the current turn — strong, but only this turn
3. CLAUDE.md project rule — treated as overriding, always present as instruction
4. A mechanical gate (structural guard / test / pre-commit that FAILS) — zero discretion

**How to apply — when a lesson is violated ≥2×, escalate it:**
- Code-pattern lesson → write a structural guard (this repo has ~25 AST guards
  with shrink-only allowlists; the guard's failure list IS the work-list and it
  stays red until done). See [[feedback_fitness_functions_pattern]],
  [[feedback_structural_guards_pin_production_paths]].
- Process / communication lesson (don't-claim-ready, verify-before-asserting)
  → put it in CLAUDE.md as a gate, and make verification an OBSERVABLE step
  (paste the grep / evidence before claiming "done").

Do not promise "I'll remember next time" — that is the level-1 lever that
already failed. Build the gate.
