---
name: feedback-no-ready-claims
description: "Stop using the word \"ready\". Describe raw state — origin head, local commits ahead, CI's last verdict on what — and let the user decide"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: acdcab63-786c-4cc7-9c58-54f2c30d2c24
---

Do not say "ready", "ready to push", "looks good", "verified", "clean", or any equivalent claim about the future state of CI based on local observation. Those words are predictions, and I make wrong predictions repeatedly enough that the user has stopped trusting them.

**Why:** Across this session I have said "ready" or equivalent multiple times when:
- Local tests passed but CI hadn't been re-run against my fix
- I had unpushed local commits and described state as if origin matched local
- I narrow-scoped my pytest run to the files I touched and called the whole PR ready

Each time the user catches it because CI is the actual verdict and my "ready" was a prediction based on incomplete local evidence. The user said: "we failed unit and e2e tests again?? So we aren't getting better at this? Why not?" Honest answer: because I keep using "ready" language and the underlying optimism bias doesn't go away just because I write better memories.

**How to apply — replace "ready" with raw state:**

Bad (what I keep doing):
> "Ready for push — 22/22 tests pass locally"

Good (what I should do):
> "Local commit `d794ad1ea` exists, not on origin yet. Origin head is `1d0974ec5`. CI last ran against `1d0974ec5` and reported: Unit fail (2 sub-tests from old fixture using 'stress'), E2E fail (test_offline_mode pre-existing schema drift), 2 unrelated pre-existing schema-drift failures. My local commit fixes the 2 test_mode sub-tests; pushing it should clear them. CI will tell us; I haven't observed CI on the fix."

Specifically NEVER:
- Predict CI state from local results
- Use "ready", "good", "clean", "verified", "all set", "should pass" without immediately attaching what hasn't actually been observed
- Bundle "tests pass locally" with the conclusion "this is done"

Specifically ALWAYS:
- `git log @{u}..HEAD` before any state claim. If non-empty, name what's local-only.
- `gh pr checks <num>` to read CI's actual verdict, not predict it.
- State observations as observations: "I ran X. It output Y." Not "X works."
- Distinguish "fixed locally" from "verified on CI." Use both phrases explicitly when both are relevant.

**Why this might actually work where memory-sharpening hasn't:** The word "ready" is short and easy to type. Banning it specifically forces the longer raw-state description, which forces the missing fact ("CI has not seen this") to surface. The friction of typing the longer description is the point.

Related: [[feedback_verify_before_asserting]] (the broader rule), [[feedback_atomic_breaking_changes]] (specific case from this session). This memory is narrower than both — it's a single banned word, not a workflow. The hope is narrower = stickier.
