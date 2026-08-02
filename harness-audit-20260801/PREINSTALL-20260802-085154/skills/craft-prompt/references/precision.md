verified: 2026-07-14 · sources: skill-catalog §2; prompt-craft §2.1; goal adjective: defined

# Axis: precision — how explicit terms and contracts are

| Level | Contract | Prompt fragment |
|---|---|---|
| P0 loose | conversational; terms as commonly understood | (none) |
| P1 terms-defined | jargon defined at first use | `Define any term of art at first use; do not assume shared shorthand.` |
| P2 explicit-contracts | outputs carry stated structure; inputs named | `State the exact output structure before producing it; name your inputs and what you did with each.` |
| P3 schema-constrained | machine-checkable output | `Emit output conforming to the provided schema exactly; validate before emitting; no prose outside the schema.` |

Lint hooks: undefined invented labels (P1+); output deviating from declared structure (P2+); non-conforming JSON (P3 — mechanically checkable). Rubric hooks: could a parser (P3) or a checklist (P2) verify the output without judgment calls?

Interactions: P3 implies structured-output tooling where the surface supports it (schemas beat prose promises); craft-prompt renders P-level into the *produced* prompt's output contract. The engine's own skills run P2 (contracted sections) — that's what makes them evaluable.
