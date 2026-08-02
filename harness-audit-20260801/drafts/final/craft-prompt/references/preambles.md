verified: 2026-07-14 · sources: example-corpus §1.5 (OpenAI tool_preambles verbatim; Codex cadence)

# Policy block: preambles

Progress-narration contract for agentic work: what the agent says before, during, and after tool use. Keeps users oriented without narration spam.

## Canonical text

```
Before the first tool call, state the goal in one sentence and your plan in 1-2
sentences. While working, give brief updates only at new phases or plan-changing
discoveries — not per tool call. Finish with a summary distinct from the plan:
what changed, what was verified, what remains.
```

## Cadence variants

- Tight (codex-style): `1-sentence acknowledgement, 1-2 sentence plan; most updates 1-2 sentences; longer only at real milestones.`
- Structured (gpt tagged): wrap the canonical text in `<tool_preambles>...</tool_preambles>`.
- Long-horizon: add `Update the plan/progress note when reality diverges from it — silently diverging plans are worse than no plan.`

## Interactions

Voice axis sets register (terse-engineer: drop the "friendly" tone entirely; narrative: full sentences, no fragments). Density axis caps update length. In review stance, the preamble names the scope being swept instead of a plan.
