verified: 2026-07-14 · sources: skill-catalog §2; policy-blocks/verbosity; goal adjective: concise

# Axis: density — how much output per unit of substance

| Level | Contract | Prompt fragment |
|---|---|---|
| D0 exhaustive | completeness over brevity | `Be comprehensive; do not omit relevant detail for the sake of length.` |
| D1 balanced | overview + supporting points | `One overview paragraph, then the key points — no padding, no repetition.` |
| D2 tight | per-section sentence caps | `Keep each section to <=N sentences. Cut anything that does not change the reader's next action.` |
| D3 hard contract | exact structure, numeric limits | `Emit exactly the named sections with the stated limits; nothing outside them.` |

Lint hooks: output exceeding declared shape; repeated content; filler openers ("Certainly," "Great question"). Rubric hooks: length-vs-contract conformance; redundancy count; information kept per token (spot-check: could a sentence be deleted without loss?).

Interactions: density constrains OUTPUT, never the thinking; judge scoring must length-normalize (verbosity bias) so D0 outputs don't win by volume. Preambles block inherits the level.
