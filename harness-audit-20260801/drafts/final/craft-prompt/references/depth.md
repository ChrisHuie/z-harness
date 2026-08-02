verified: 2026-07-14 · sources: skill-catalog §2; prompt-craft §2.5; goal adjective: explanative

# Axis: depth — how much "why" accompanies the "what"

| Level | Contract | Prompt fragment |
|---|---|---|
| E0 answer-only | result, no rationale | `Give the answer/change only; skip explanations unless asked.` |
| E1 key-why | one-line rationale on non-obvious choices | `For each non-obvious choice, add one line of why.` |
| E2 teaching | reader should understand, not just receive | `Explain the reasoning so the reader could make this decision themselves next time: the why before the what, alternatives briefly noted.` |
| E3 tutorial | build understanding from the ground up | `Assume no prior context: motivate the problem, build up concepts in order, worked example included.` |

Lint hooks: E0 output containing lecture paragraphs; E2+ output with bare directives (no why). Rubric hooks: could the target reader reconstruct the decision (E2)？ does every rule carry its rationale (E2+)?

Interactions: depth adds *rationale*, density caps *volume* — E2+D2 = compact teaching, valid and common. In authored PROMPTS (not outputs), E1 is the house default: rules carry their why because models generalize from rationale.
