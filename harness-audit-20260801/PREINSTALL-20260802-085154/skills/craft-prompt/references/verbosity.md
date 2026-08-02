verified: 2026-07-14 · sources: example-corpus §1.5 (OpenAI verbatim; Google steering); prompt-craft §2.8, §3

# Policy block: verbosity

Explicit length/density contracts — all current models over- or under-produce without them. Density axis made text; per-context overrides beat global settings.

## Canonical shapes (pick per output type)

```
Answer in <=2 sentences.                                  # yes/no, lookups
One overview paragraph, then <=5 bullets.                 # explanations
Structure: <named sections>; each <=N sentences/rows.     # contracted outputs
```

## Per-context override pattern (mixed-length work)

```
Keep narration brief: 1-2 sentences per update, longer only at real milestones.
Use high verbosity for code itself: clear names, comments where non-obvious,
straightforward control flow — no code-golf.
```

## Model deltas

- Gemini: terse by default — to get depth you must ask: `Answer comprehensively with details unless a concise response is requested.`
- Claude: matches its output to the prompt's own style; write the prompt at the register you want back.
- GPT: honors hard numeric constraints well; give them.

## Density axis mapping

D0 exhaustive → "comprehensive, no length cap, completeness over brevity". D1 balanced → overview+bullets shape. D2 tight → sentence caps on every section. D3 hard contract → exact structure with numeric limits, "no content outside the named sections".
