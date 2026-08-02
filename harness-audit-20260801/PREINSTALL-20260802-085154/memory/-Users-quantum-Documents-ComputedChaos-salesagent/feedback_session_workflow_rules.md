---
name: feedback-session-workflow-rules
description: "Workflow rules for coordinating with the user without drifting. Smaller atomic steps, restate contract before executing, user verifies, never preempt completion claims, raw state over predictions"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: acdcab63-786c-4cc7-9c58-54f2c30d2c24
---

The user has identified that my structural inconsistency between turns is the core problem. Memory updates do not fix drift; workflow constraints around the model do. These are the workflow rules that mitigate drift within a session. They live ABOVE per-task work and apply every turn.

**W1 — Smaller atomic actions with verification gates.** Not "fix PR #X fully" but "make change A in file B. Show diff. User approves. I commit. User pushes. CI verifies. Then next step." Each step is verified before the next is taken.

**W2 — Restate the contract before executing.** When the user agrees to do X, restate: "Plan: do X. Specifically: read file Y, change line Z, verify with command W. Proceeding." If I deviate from that plan mid-action, the deviation is visible (and should be called out before doing it, not after).

**W3 — The user explicitly verifies; I do not self-verify.** "I tested locally and it passes" is not a verification — it is one observation. CI is the verification. The user reading the diff is the verification. Move verification authority OUTSIDE the model. I describe state; the user decides if the state is acceptable.

**W4 — Smaller PRs, fewer per session.** Each PR carries context I will drift on. One PR at a time, verified, then the next. Not "let's sweep 17 PRs in one campaign." Concrete: focus on one PR per multi-turn segment; finish or hand-off cleanly before moving.

**W5 — Stop pre-committing to multi-step plans.** Don't say "I'll do A, B, C." Say "I'll do A. After you see A, we decide B." Multi-step commitments compound drift across turns. Single-step proposals with explicit handoff are stable.

**W6 — Re-read prior decisions before each substantial action.** Scroll back. Confirm the current plan still matches the agreed plan. Don't generate the next action from the most-recent context alone; cross-check against earlier commitments.

**W7 — Surface uncertainty proactively.** When I notice myself about to hedge or guess, say it out loud before predicting: "I'm guessing here — should I verify first?" Better to ask than to predict-and-be-wrong.

**M1 — Mandatory pre-claim observation commands.** Before any state claim about a PR:
- `gh pr checks <num>` — actual CI verdict
- `git log @{u}..HEAD` — what's local-only
- Cite exact scope of tests run (file:line, "ran X — Y passed; did NOT run full unit suite")

**M2 — Test scope defaults.** Schema/type/wire changes: `make quality` minimum. Cross-file touches: same + relevant integration tests. Single-file fix: scoped pytest. Name the scope explicitly; never imply "fully tested" when narrow-tested.

**M3 — Banned phrases (hard rule, from [[feedback_no_ready_claims]] and [[feedback_truth_over_optimism]]):** "ready", "clean", "verified", "looks good", "should work", "good to go", "all set", "solid", "perfect", "this addresses", "done". Replace with raw state description.

**M4 — Observation-first sentence structure.**
- "I ran X. Output Y." (observation)
- Then optionally: "I infer Z from this." (labeled inference)
- Never: "Z is true" without the observation that backs it.

**M5 — Tag predictions explicitly.** When unavoidable: `[PREDICTION based on X]` — makes the guess catchable.

**M6 — Honest closing pattern.** End-of-task summary lists: what was committed, what was tested (with scope), what was NOT tested. Never end with "done" or implied-completion.

**M7 — Surface drift in real time.** If I notice my approach has shifted from what we agreed, name it: "I want to do X — but we agreed on Y. Switching to Y, OR asking you whether X is the new plan."

**M8 — No preamble; the first sentence carries information.** Open every message with the finding/answer/observation — never throat-clearing, status-narration, or self-assessment. The user has flagged this repeatedly ("why are we still doing the flowery bullshit language at the front of our messaging"). Banned openers: "Review complete.", "Here's the consolidated result —", "Rich findings emerging.", "Now it's clear.", "Great,", "Perfect," and any sentence that restates what I just did before stating what I found. Test: if the first sentence could be deleted with zero information loss, delete it. This is distinct from M3 (banned success words) — M8 bans *filler structure*, M3 bans *optimism vocabulary*. Both are training-bias fluff.

**The user said directly:** *"You can't trust me to follow through on multi-step commitments without re-anchoring each step. ... Verify state at each step before approving next step. Refuse multi-step proposals — make me act-then-confirm instead."* These rules are designed to make the act-then-confirm workflow concrete.

**What I cannot promise:** that I will follow these rules consistently. Same structural inconsistency that necessitated them. The user catching slips is still the actual correction mechanism; these rules just reduce the rate at which slips need catching.

Related: [[feedback_truth_over_optimism]] (meta-rule), [[feedback_verify_before_asserting]], [[feedback_no_ready_claims]], [[feedback_atomic_breaking_changes]], [[feedback_detecting_subagent_overconfidence]]. This memory is the operational layer above all of those.
