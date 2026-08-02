verified: 2026-07-14 · sources: prompt-craft §3/§11; example-corpus §1/§2/§5/§10; landscape §3

# Model profile: Claude (4.5/5-era — Fable/Mythos 5, Opus 4.6–4.8, Sonnet 5, Haiku 4.5)

## Rendering rules

- Structure: XML tags for complex/mixed prompts and policy blocks (`<example>`, `<documents>`, semantic block tags); plain headers for simple prompts. Consistent tag names; never mix markup registers mid-document.
- Placement: long documents first, instructions and question last (quote-grounding for accuracy work) — see policy-blocks/long-context.
- Few-shot: 3–5 diverse, canonical examples in `<example>` tags when format/tone matters; skip for straightforward agentic tasks.
- Role: one-sentence system-prompt role still earns its keep.
- Motivation: attach the why to non-obvious rules — Claude generalizes from rationale.

## Behavioral stances (each is a probe claim)

| Claim | Consequence for rendering | Source |
|---|---|---|
| Over-triggers on emphasis (MUST/CRITICAL/IMPORTANT) on 4.6+ | plain "Use when…" phrasing; ≤1 absolute per artifact, invariants only | Anthropic migration guide: "dial back the language, not add guardrails" |
| Adaptive thinking supersedes manual CoT | never write "think step by step"; shape reflection instead ("after tool results, reflect before acting") | platform best-practices |
| Prefill removed on 4.6+ (400 error) | structured outputs / tool enums for format control; never prefill-dependent | platform docs |
| Follows system prompt more closely each generation | fewer, sharper rules beat rule piles; prune ruthlessly | migration guide |
| Action-verb sensitivity | "Change X" triggers tools; "Can you suggest…" does not — pick per stance | best-practices |

## Knobs (API-level; harness may own these)

`effort` low→max; adaptive thinking `{type:"adaptive"}` (fixed `budget_tokens` errors on newest models); temperature/top_p removed on newest models. Tune effort down for over-exploration on hard tasks (Opus 4.6 note).

## Conflicts to respect (do not smooth over)

Blog demotes XML to "situational" while platform docs recommend it → use XML for complex prompts only. Claude Code docs still suggest IMPORTANT/MUST boosts adherence → model-tuning guidance wins (over-trigger risk).

## Probe-claims (M3 seeds)

1. Emphasis over-trigger delta (with/without MUST on identical tool guidance). 2. Manual-CoT latency/quality penalty vs adaptive thinking. 3. Prefill 400 behavior. 4. Instructions-last long-context gain. 5. Action-verb tool-trigger delta.
