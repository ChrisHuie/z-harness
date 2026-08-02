---
name: feedback_direct_measurement_beats_inference
description: "When a quantity is in the data, measure it — do not reconstruct it. Careful inference lost to a one-command measurement twice in one session, and a two-arm experiment shipped a null edit that a third arm caught."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: e2367c8b-0c8b-43ae-a5d4-98ce3fbcecea
  modified: 2026-08-02T03:32:31.035Z
---

Two failures of the same shape, 2026-08-01:

**1. Reconstruction beat by one command.** Subagent `output_tokens` looked like a stub
(median 3 while carrying 1–3k chars). An agent built a validated regression over 6,211
transitions, back-tested it, and estimated 35.73M. A second agent reasoned the final-call
outputs were 4x the mean and "corrected" it upward to 38.6–45.7M. **The true value —
35,949,358 — was in the transcript the whole time**, in the LAST record of each `requestId`
rather than the first. The regression was accurate to 0.6%; the reasoned correction made it
worse. Nobody checked whether the number was simply retrievable.

**2. A two-arm experiment shipped a null edit.** Testing whether a "cap findings at ~5" rule
suppressed review recall: capped arm 27% recall, arm with the cap removed AND an explicit
enumeration mandate 100%. Conclusion drawn: remove the cap. **A third arm — cap sentence
deleted, nothing added — got 23%.** Deleting the cap does NOTHING; the entire effect was the
positive instruction ("list every site it covers, one per line"). Two arms would have shipped
a confident, precise, wrong fix.

**How to apply.**
- Before reconstructing a quantity, ask whether it is recorded somewhere you have not looked.
  Check every record for a `requestId`/group, not just the first.
- An A/B that changes two things at once tells you the pair matters, not which one. If the
  recommendation is "remove X", run the arm that removes ONLY X.
- Prefer the cheap decisive experiment BEFORE the broad analysis. Broad analysis ordered first
  produces waves that each "discover" what a five-minute test would have settled, and the cost
  is paid by the user.
- A prediction that fails is a result. Record it: "predicted ~97%, measured 53%, 40 points
  unexplained" is more useful than quietly dropping the prediction.

Related: [[feedback_verify_with_the_same_instrument]], [[reference_claude_code_measurement_traps]]
