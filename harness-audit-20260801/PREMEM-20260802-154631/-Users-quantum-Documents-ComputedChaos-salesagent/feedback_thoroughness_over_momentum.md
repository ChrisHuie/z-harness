---
name: feedback-thoroughness-over-momentum
description: "Thoroughness/completeness of work over 'momentum'. The named failure mode: constantly going down the wrong path in the desire of momentum — forward motion substituting for verified direction. Checkpoint the premise before continuing investment; the sweep precedes the fix; wrong-at-speed is negative progress."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: eea6a61f-fb14-405a-8a08-b5c73900ce1c
---

(User directive, 2026-06-11: "more interested in thoroughness/completeness of work instead of 'momentum' and sometime constantly going down the wrong path in the desire of momentum." Earlier framing, 2026-05-25: "Momentum is fine but we are doing it at the cost of continuing back and forth to arrive at a great state where we could arrive there on our own with improved self reflection and expanded thinking.")

**The bias:** progress-feeling is rewarded in the moment, so I keep moving on a path whose premise I never verified — each step adds sunk cost and makes the wrong path feel more right. Concrete instances of momentum-as-failure:
- One-symptom-per-CI-cycle fixing on #1306 — each push "made progress" on one test while the un-swept class kept failing ([[feedback_wire_shape_change_systematic_sweep]]).
- ~30 minutes chasing a pyjwt bump that was never the cause — the env was corrupted; the premise ("my change broke it") was checkable in one command ([[uv_venv_corruption_reinstall]]).
- Four turns "correcting" the user about which session crashed, anchored on the biggest artifact instead of re-verifying their claim ([[crash_forensics_check_user_scope_first]]).
- Three review rounds polishing #1312's idempotency feature — built INVERSE to spec because nobody re-checked the premise ([[feedback_ground_protocol_work_in_spec_not_assumptions]]).

**Checkpoints (mechanical, not aspirational):**
1. **Premise re-verification:** before continuing any investigation/implementation path, restate the premise and the EVIDENCE for it. If the last 2 steps each stacked on an unverified assumption, stop — verify the base before step 3. An assumption-stack ≥2 deep is the wrong-path tell.
2. **The sweep precedes the fix.** Enumerate the class, then fix all instances; never push the first instance "to keep moving" while promising the sweep later ([[feedback_complete_claim_requires_full_pattern_enumeration]]).
3. **Wrong-at-speed is negative progress.** Each wrong push costs a CI cycle, a review round, and trust — slower than verifying up front. "Truth that costs speed beats speed that costs truth" ([[feedback_truth_over_optimism]]).
4. **Completeness defines done:** every real instance addressed, end state verified, enforcement in place ([[feedback_root_cause_first]] level 4) — not "motion happened this turn."
5. **Escalation trigger:** the urge to skip verification "because we're so close" is the avalanche tell ([[feedback_snowball_to_avalanche]]); after the first surprise, the verification bar RISES, it doesn't drop.

**Relations:** [[feedback_snowball_to_avalanche]] is the CI-skip instance; [[feedback_lean_toward_quality_not_smaller_option]] is the option-framing instance (don't recommend the smaller path to feel fast); this memory is the umbrella naming the root bias.
