verified: 2026-07-14 · sources: prompt-craft §7 (planning/architecture), §2.1 (outcome contract), modes-and-composition §3/§7 (default stance, handoff)

# Pattern: planning

**Purpose:** choose an approach and lay out the work before any code.
**Default stance:** plan — this *is* the plan stance's task pattern; it rarely runs elsewhere.

## Method
- Explore → plan before code: do not write code yet.
- Produce 2–3 alternatives, each with its trade-offs.
- Frame as an outcome contract (goal, constraints, success criteria), not a step prescription.
- Close with a definition-of-done and an approval gate.

## Output contract
The plan artifact (`docs/plans/<slug>.md`): goal; 2–3 alternatives with trade-offs; chosen approach + steps; risks; definition-of-done. This is the input contract for the implement stance.

## Rubric hooks
- Are 2–3 genuine alternatives weighed (not one foregone conclusion dressed up)?
- Is there a definition-of-done and an explicit approval gate?
- Does it decide before coding, with no premature implementation?
