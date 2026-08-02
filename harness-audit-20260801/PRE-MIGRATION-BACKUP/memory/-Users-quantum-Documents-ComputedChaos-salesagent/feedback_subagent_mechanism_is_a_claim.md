---
name: feedback_subagent_mechanism_is_a_claim
description: "A subagent's observed symptom is evidence but its causal explanation is a hypothesis — falsify the mechanism before repeating it"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: b9324151-908f-41b4-9a0b-cdecca3d8647
  modified: 2026-07-31T11:57:58.978Z
---

When a specialist reports "X happens **because** Y", treat X as evidence and Y as a hypothesis. Before Y enters any outbound artifact, re-derive it — ideally by falsifying it: find the case where Y is absent and X still happens.

**Why:** subagents run the commands, so their symptoms are usually solid; their explanations are often reasoned, and both arrive wearing the same `[observed]` tag. Nothing in the review discipline covered this — one rule handles items inherited from a *colleague*, another handles *severity*, neither handles the causal sentence. Instance: a specialist reported inter-suite test failures and attributed them to `patch.dict(os.environ, clear=True)` wiping an env var. The failure was real and reproduced exactly; the mechanism was wrong. A one-line bisect showed the two sibling tests using `clear=False` fail identically, and the true cause was `importlib.reload` capturing an autouse mock ([[reload_captures_active_mock]]). It reached a consolidated report and was one step from a public PR comment.

**How to apply:** the tell is cheap — an explanation naming ONE cause for a symptom that has several candidates, with no experiment shown that isolates that cause. Ask "what experiment would distinguish Y from the alternatives, and did they run it?" A bisect over the reporter's own inputs is usually minutes. Encoded as review-charter §1.7d. Related: [[subagent_overconfidence]], [[root_cause_first]], [[prior_round_finding_needs_remeasure]].
