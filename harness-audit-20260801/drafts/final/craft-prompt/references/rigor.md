verified: 2026-07-14 · sources: skill-catalog §2; prompt-craft §2.9/§2.10; goal adjective: accurate

# Axis: rigor — how claims must be grounded

| Level | Contract | Prompt fragment |
|---|---|---|
| R0 best-effort | answer from knowledge; no grounding duty | (none) |
| R1 cite-when-load-bearing | decision-driving claims name their source | `Cite the source (file:line, URL, or doc) for any claim a decision rests on.` |
| R2 evidence-per-claim | every factual claim grounded; gaps declared | `Ground every factual claim in the provided material or name it as unverified. When evidence is insufficient, say so and name what is missing.` |
| R3 verify-before-claim | claims checked by action before assertion | `Do not assert something works or is true until you have verified it (run it, read it, test it) — show the evidence, not the assertion.` |

Lint hooks: R2+ output containing unhedged claims without citations; "should work"/"probably" in R3 outputs. Rubric hooks: grounding rate of load-bearing claims; presence of explicit insufficiency statements when material is thin.

Interactions: R3 implies self-reflection shape 2; in review stance R2 is the floor (findings need mechanisms); rigor governs *claims*, not verbosity — R3+D3 is valid (verified and terse).
