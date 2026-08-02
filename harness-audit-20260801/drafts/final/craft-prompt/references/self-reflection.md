verified: 2026-07-14 · sources: example-corpus §1.3 · https://developers.openai.com/cookbook/examples/gpt-5/gpt-5_prompting_guide · https://developers.openai.com/cookbook/examples/gpt-5/gpt-5-2_prompting_guide · ◐ https://www.philschmid.de/gemini-3-prompt-practices (Google checklist; re-verify at landscape-refresh)

# Policy block: self-reflection

A verification pass before finalizing. Two shapes: a hidden quality rubric (open-ended generation) and a concrete re-scan (factual/safety-sensitive output). Steers internal reasoning depth — never asks the model to externalize chain-of-thought.

## Shape 1 — hidden rubric (creative/zero-to-one work; gpt/claude)

```
<self_reflection>
Before answering, privately construct a 5-7 category rubric for what a world-class
result looks like for this task. Do not show the rubric. Iterate internally until
your response would score at the top of every category.
</self_reflection>
```

## Shape 2 — concrete re-scan (accuracy-sensitive output; all models)

```
Before finalizing, re-scan your answer for: unstated assumptions; numbers or claims
not grounded in the provided context; overly strong language ("always", "guaranteed").
Soften or qualify what you find, and state assumptions explicitly.
```

## Shape 3 — intent check (Google-derived; conversational/persona work)

```
Before returning, verify: does this answer the user's intent, not just their words?
If an assumption filled a gap, is it flagged?
```

## Parameterization

Rigor axis: R2 → shape 2; R3 → shape 2 + evidence-per-claim requirement. Calibration axis C2+ → add shape 3's assumption-flagging line. Skills with output contracts: point shape 2 at the contract ("re-check each contract section is present and conformant").
