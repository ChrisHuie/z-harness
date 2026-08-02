verified: 2026-07-14 · sources: prompt-craft §7 (research/synthesis), §6 (breadth fan-out), modes-and-composition §3 (default stance)

# Pattern: research

**Purpose:** synthesize an evidence-backed answer from sources.
**Default stance:** explore (read-heavy, report-only) — also runs under **plan** when the research feeds a decision.

## Method
- Extract-then-synthesize: gather the evidence first, then reason over it.
- Attach a citation to every claim.
- Return structured output, not a wall of prose.
- Grant explicit permission for "insufficient evidence" — say so rather than invent.
- Parallelize breadth-first fan-out (read-heavy work); synthesize and write in one context.

## Output contract
Structured findings; each claim carries a citation to its source; an explicit "insufficient evidence" verdict is available and used where the evidence does not support a claim.

## Rubric hooks
- Does each claim carry a citation to a real source?
- Is extraction separated from synthesis (grounding precedes conclusion)?
- Does it flag insufficient evidence instead of fabricating an answer?
