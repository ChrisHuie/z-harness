---
name: feedback_verify_with_the_same_instrument
description: "Every 'verification' done with a looser instrument than the thing it checks produces a confident WRONG answer. Use the same matcher the original used, or state plainly that you did not."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: e2367c8b-0c8b-43ae-a5d4-98ce3fbcecea
  modified: 2026-08-02T03:32:04.411Z
---

Spot-checking a careful result with a fast grep is not verification — it is a new, weaker
measurement that will disagree, and the disagreement will look like the original was wrong.

**Observed 2026-08-01, eight times in one session** (four by the orchestrator, four by
subagents), every one producing a confident wrong answer in the reassuring direction:

- `grep 'review-charter.md'` (a MENTION) vs the file's H1 (its CONTENT) → 79%/89% vs a true
  71.8%. **91.6% of agents that never loaded a file still cite it by name.** Citation carries
  zero information about reading.
- Counting findings in consolidated artifacts when the rule under test binds individual
  agent reports → 16% vs a true 81.8%. Right regex, wrong denominator unit.
- Deduping JSONL by `requestId` and keeping the FIRST record, when one API call writes one
  record per content block → dropped nearly every tool_use.
- A basename-guesser producing 15 fake "phantom citations".
- An all-digit SHA excluded as "not a SHA", silently falling back to the merge-base → 3 fake
  "file does not exist" defects.
- A naive `file.py:NNN` regex ignoring bare-line continuations and ranges → 5 false "dropped
  finding" flags out of 6.
- The string "does not exist" appearing in a memory's own prose → 474 fake failed reads
  (true: 3 of 7,800).

**How to apply.** Before checking someone's number, find the instrument they used and use
that one — the repo's own matcher, their script, their filter. If you use a different one,
say so and treat any disagreement as *two measurements of different things* until you have
identified which choice drives the gap. State the filter with the number, always.

**Why this matters more than it sounds.** These errors are not random: they all resolved
toward "the earlier work was wrong" or "the thing is fine", which is the direction that ends
inquiry. A wrong instrument does not produce noise, it produces false confidence.

The agents whose results held up were consistently the ones who reported their own
instrument errors BEFORE reporting results. Do that.

Related: [[reference_claude_code_measurement_traps]], [[feedback_direct_measurement_beats_inference]]
