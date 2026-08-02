verified: 2026-07-14 · sources: prompt-craft §2 (all 13 universal principles), §11.4 (few-shot resolution), example-corpus §10, landscape §3/§7 (harness→model mapping)

# Model profile: neutral (model-unknown rendering)

A **first-class profile, not an absence** — the default for multi-model harnesses (Copilot, opencode, Cursor) and any target whose model is unknown. Ships exactly the cross-vendor universal core, rendered conservatively.

## The universal core, as rendering rules (all 13)
1. Outcome contract over step prescription — goal, constraints, success criteria, output format; explicit action verbs.
2. Positive instructions — say what to do, not what to avoid.
3. One structural delimiter per document — do not mix XML and Markdown.
4. Placement — large context first; instructions and the question last, with an anchor phrase.
5. Motivation with rules — state *why* a rule exists.
6. Few-shot — few, diverse, canonical, consistently formatted (3–5 max).
7. Absolutes only for invariants; everything else as conditional decision rules.
8. Explicit verbosity/length contracts ("≤2 sentences").
9. Uncertainty policy stated — permit "I don't know"; on ambiguity, ask 1–3 questions or present 2–3 interpretations flagged.
10. Self-verification pass against the original constraints; show evidence, not assertion.
11. Persistence clause for agents, paired with an autonomy boundary and escape hatch.
12. Every line earns its token cost.
13. Zero contradictions — the single highest-leverage mechanical check.

## What neutral rendering OMITS
- No vendor-specific policy blocks or per-family accents.
- No emphasis beyond a single invariant — no CAPS/MUST escalation.
- Markdown headers only — no XML policy tags (tag-following varies by model).
- At most 1–2 canonical few-shots, and only to pin output *format*.
