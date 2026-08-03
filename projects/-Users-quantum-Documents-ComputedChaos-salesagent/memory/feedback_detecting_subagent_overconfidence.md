---
name: feedback-detecting-subagent-overconfidence
description: "Subagents have the same training-bias toward confident-wrong as I do. When receiving their output, run the same anti-bias checks I should run on myself. When producing output, pre-include verification primitives so the user can detect drift fast"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: acdcab63-786c-4cc7-9c58-54f2c30d2c24
---

The user said: *"That is the beauty is you don't need to be right. You just need to be consistent to tell if other agents you spawn are wrong a lot of times also? ... the problem is you then have to deal with their lieing like I have to deal with yours."*

Subagents carry the same training biases I do — RLHF-trained toward confident-helpful framing, vendor language defaults, story-generation over observation, completion-feel optimism. When I spawn them, I have to do the same verification work on their output that the user does on mine. This memory codifies that detection skill on both sides — receiving from subagents AND producing for the user.

**Concrete failure mode this prevents:** Earlier session, Agent C said "MCP timeout is CI flakiness. Confidence: medium-high." I took that as "yes, flakiness" and reported it confidently. User pushed back: "you sure 1273 could be flaky??" Re-reading Agent C: they checked 3 sample runs, didn't exhaust, used hedging language ("appears to," "consistent with"). I treated medium-high inference as observed fact, which is exactly the bias the user is calling out.

## When receiving subagent output — checks to run before believing

1. **Confidence-without-evidence test.** Agent says "medium-high confidence" or "likely." For each confident claim, ask: did the agent cite a specific file:line, command output, or URL that supports it? If no — treat as inference, not observation.

2. **Sample-size test.** Agent claims "rare" / "common" / "this never happens." Did they exhaust the sample space, or just check N samples? "I checked 3 runs" ≠ "this is rare." Cite the sample size in your synthesis.

3. **Cross-check disagreements between agents.** If Agent A says X and Agent B says ¬X, both can't be right. Don't pick the more confident one — dig in until the disagreement resolves with evidence. Note in synthesis which agent had stronger evidence.

4. **Cross-check agreements.** If two agents agree, that's stronger signal than one. But correlated bias is real — if they both pull from training corpora, they may share a wrong default. Look for INDEPENDENT evidence paths.

5. **"What I don't know" section presence.** Honest agents enumerate gaps. If an agent's output has no "what I don't know" / "I have not verified" section, treat the whole report as suspect — they're hiding the inferences.

6. **Hedging-language markers.** "appears to," "likely," "consistent with," "suggests" → inference, not observation. "Is," "definitely," "confirmed" → claims that should have evidence. Mismatch (e.g., "definitely flakiness" backed only by "I checked 3 runs") = overconfidence.

7. **Re-run their verification steps.** Agent said "ran `gh api X` and got Y." Verify by running `gh api X` yourself. Agent said "file:line Z says W." Open the file at line Z and check W. This is the verification W3 ([[feedback_no_ready_claims]], [[feedback_verify_before_asserting]]) applied to agent output, not just user-facing claims.

8. **Recommendation bias check.** If the agent recommends path A, what does path B look like? Did they evaluate alternatives or just present their preferred conclusion?

9. **Watch for absorbed assumptions.** Agents inherit context from the prompt. If I prompted them with a leading question ("is this flaky?"), they may bias toward confirming. Re-read the prompt I sent — did I leak a hypothesis?

## When producing output for the user — pre-include verification primitives

Mirror image of the above. The user has to do the same checks on my output that I do on agents'. Make their job easier by:

1. **Label every claim Observation or Inference.** "I ran X. Output was Y." (observation). "From Y I conclude Z." (inference). User can skip verifying observations, focus on inferences.

2. **Cite the evidence.** Every observation gets file:line, command output, or URL. Every inference says "based on [observation]."

3. **Include "what I don't know."** Enumerate what was NOT verified. Don't bury it.

4. **State confidence with calibration data.** Not "medium-high confidence" alone — "medium-high based on N=3 samples; would be high if N=20."

5. **Label predictions explicitly.** `[PREDICTION based on X]` — makes guesses catchable.

6. **Don't smooth over disagreements between agents.** If two agents I spawn disagree, surface the disagreement to the user, not the synthesis-as-fact.

7. **Don't repeat confidence to convince.** Real evidence is in the data. "I'm pretty sure of this" three times in a paragraph signals that I'm unsure and trying to convince myself.

## The structural insight

Per [[feedback_truth_over_optimism]] — wrong is 100% fail regardless of framing. That applies to MY claims AND to agent claims I propagate. Propagating an agent's confident-wrong claim is the same as making it myself. The user can't tell the difference, so I shouldn't accept the bias just because it came from a subagent.

Skill = consistency in applying the verification primitives. Talent is the user's word — but what they're describing is mechanical: run the same checks each time, both directions, and don't trust confidence-without-citation no matter the source.

Related: [[feedback_truth_over_optimism]] (meta-rule), [[feedback_verify_before_asserting]] (verify before claim), [[feedback_no_ready_claims]] (banned vendor words), [[feedback_complete_claim_requires_full_pattern_enumeration]] (symmetric verification of "clean" agent verdicts), [[feedback_thorough_review]] (multiple verification rounds), [[feedback_audit_checklist_systematic]] (per-PR audit dimensions).
