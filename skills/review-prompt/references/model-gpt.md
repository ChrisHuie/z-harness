verified: 2026-07-14 · sources: prompt-craft §3/§11; example-corpus §1/§5/§10; landscape §3 (GPT-5.x era: 5.2–5.6 Sol/Terra/Luna)

# Model profile: GPT-5.x

## Rendering rules

- Structure: Markdown document + XML-tagged behavioral policy blocks (`<persistence>`, `<context_gathering>`, `<self_reflection>`) — OpenAI's own house style; "use Markdown only where semantically correct."
- Placement: stable instruction blocks first (prompt-cache prefix), volatile content last.
- Few-shot: zero-shot first; add examples only for format-critical output.
- Instruction register: imperative, verb-first, one directive per line; colon-led sub-structure ("Goal:", "Method:") inside blocks; quantified-but-tilde-hedged thresholds ("~70%", "1–3 questions").

## Behavioral stances (each is a probe claim)

| Claim | Consequence for rendering | Source |
|---|---|---|
| Hyper-literal instruction following (5.2+) | scope-discipline block near-mandatory ("exactly and only"); say what you mean precisely | 5.2 prompting guide |
| Contradictions burn reasoning tokens and destabilize | zero-contradiction lint is critical-severity for gpt targets | GPT-5 guide |
| Manual CoT unnecessary/harmful on reasoning models | no "think step by step"; steer internal depth via hidden rubrics instead | reasoning best-practices |
| Emphasis de-emphasized; absolutes for invariants only | decision rules ("If X, then Y") replace MUST-phrasing | 5.5-era guidance (secondary) |
| Persistence clauses still earn their place | render persistence + escape hatch for autonomous work | 5.1/Codex guides |
| Verbosity needs explicit numeric contracts | always emit a length shape | 5.2 guide |

## Knobs

`reasoning_effort`: none (5.2 default) → xhigh+ — also modulates tool-calling eagerness; `verbosity` param + per-context prose overrides; Responses API `previous_response_id` reuses reasoning across turns. Codex-side: model_reasoning_effort naming in flux (xhigh vs "Extra High"/Max/Ultra) — verify before pinning.

## Probe-claims (M3 seeds)

1. Contradiction-cost delta (planted-conflict prompt vs clean). 2. Scope-creep rate with/without "exactly and only". 3. Zero-shot vs 3-shot on format task (no gain expected). 4. Persistence-clause completion-rate delta. 5. Numeric verbosity-contract adherence.
