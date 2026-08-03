---
name: feedback-lean-toward-quality-not-smaller-option
description: "When presenting binary options (smaller/safer vs larger/better-end-state), I default to recommending the smaller. User wants the larger. Quality > momentum when both arrive at the same final state, just via different paths."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: acdcab63-786c-4cc7-9c58-54f2c30d2c24
---

User feedback (PR #1306 audit session, 2026-05-25):
> "we are quality focused and we need to heir on more effort, higher workload, better end result... is often preferable to quick fix or small wins. Momentum is fine but we are doing it at the cost of continuing back and forth to arrive at a great state where we could arrive there on our own with improved self reflection and expanded thinking"

**The pattern I keep falling into:**
When presenting a choice between (a) "smaller, document the gap" and (b) "bigger, fix it properly," I recommend (a) by default. The user consistently picks (b). The net result: more turns, same final state, slower arrival.

**Recognizable triggers:**
- "Document as known-deviation" / "Defer to follow-up PR" / "Note in PR description" → red flag, that's the smaller option
- "Run a focused sub-suite" vs "Run the full thing" → I lean focused; user wants full
- "Address a reviewer's literal ask" vs "Address ask + the obvious next-step that completes the architecture" → I lean literal; user wants completion

**How to apply going forward:**
- When designing options, **lead with the better-end-state option, not the smaller one**. Default recommendation is the higher-quality path.
- Treat scope expansion that **completes the architectural goal** as default-yes (already captured in [[feedback_principled_scope_expansion]]; this memory adds: I should propose it without being asked).
- Self-reflection check before any "option A vs B" framing: "Am I offering A because it's actually correct, or because it's quicker and I'm optimizing for shipping?" If the latter, drop A.
- "Expanded thinking" = walk the architectural implications all the way to the end state, then describe what shipping the partial vs full version looks like. If the full version is reachable in this session with proper care, propose it as the path.

**Don't conflate this with:**
- [[feedback_no_unsafe_autofix]] — that warns against UNRELATED scope expansion; this rule applies when the expansion is the architectural completion of the principal.
- [[feedback_snowball_to_avalanche]] — that warns about uncaught compounding failures; this rule warns about under-committing to the right end state in the first place.

**Concrete behavioral change:**
When I'd normally write "I lean A — keeps scope clean," instead write "**B** — finishes the architectural goal; here's the work and the verification plan." Skip the user-prompted upgrade.
