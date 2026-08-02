verified: 2026-07-14 · sources: prompt-craft §7 (documentation), §2 (positive instructions), modes-and-composition §3 (default stance)

# Pattern: documentation

**Purpose:** document intent so a reader can act, grounded in the real code.
**Default stance:** implement (writes docs) — also runs under **explore** for audience analysis and outlining.

## Method
- Declare the audience and the Diátaxis type: tutorial / how-to / reference / explanation.
- Document intent and the "why", not implementation line-by-line.
- Ground every claim in actual code — verify against source before asserting behavior.
- Use the structure the chosen Diátaxis type calls for; positive, direct instructions.

## Output contract
Stated audience + Diátaxis type; content shaped to that type; every factual claim traceable to a specific place in the code.

## Rubric hooks
- Is the audience and doc type declared and actually honored?
- Is every claim grounded in real code (no invented behavior)?
- Does it convey intent rather than restate the implementation?
