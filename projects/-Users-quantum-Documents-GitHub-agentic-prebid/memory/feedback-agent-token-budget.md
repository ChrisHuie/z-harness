---
name: agent-token-budget-control
description: User directive after the 2026-07-20 audit burned ~10M tokens — cap and pre-state agent counts and token cost; prefer inline main-loop work over agent fan-outs; never spawn dynamically without a stated ceiling.
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 019ecd8b-d86f-4aad-810a-5d90043858ef
  modified: 2026-07-20T16:59:25.221Z
---

During the repo audit (2026-07-20), a per-finding verification fan-out (1 subagent per finding, 93 findings + second votes, two workflows) hit ~10M tokens. The user intervened twice: "you need to reduce and control it" and "this is like 10 million tokens total. That is insane… spread that workload out or rethink it."

**Why:** Each subagent re-loads repo context from scratch, so N-per-item designs multiply reads of the same files N times. Dynamic spawning (second votes, retries) makes the count grow while the user watches, which reads as out-of-control even when bounded.

**How to apply:**
- Before any multi-agent launch, state the agent count and rough token cost up front, and get the shape right-sized: batch items by shared context (per-file, per-doc) instead of per-item.
- Prefer inline main-loop verification/synthesis when items are quote-anchored — I read each cited passage once instead of N agents re-reading it.
- No dynamic spawning without a pre-stated hard ceiling; prefer fixed volleys.
- Spread heavy work across sessions/turns if it can't be shrunk. Related: [[dont-be-eager-to-advance]].
