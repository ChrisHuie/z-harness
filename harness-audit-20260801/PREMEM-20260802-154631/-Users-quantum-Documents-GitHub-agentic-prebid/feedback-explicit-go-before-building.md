---
name: feedback-explicit-go-before-building
description: "Don't move from docs/design into writing code without an explicit go; approving one step is not approval for the next phase."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1a4d69cf-6b26-472b-b224-242ef8a4868a
---

Do NOT start building (scaffolding, code, running tooling) until the user explicitly says to build. Approval of one step is scoped to that step only — e.g. "we are good to push" authorizes the push, NOT starting R0. The docs→code transition is a strategic checkpoint the user owns; wait for a clear go.

**Why:** On 2026-07-11, after merging + pushing the docs baseline, I read "we are good to push" as momentum and immediately scaffolded R0 (pyproject/compose/gitignore). The user stopped me: "what are you doing? Didn't tell you to move to code??" No harm (nothing committed), but it broke trust in my pacing.

**How to apply:** Finish the authorized step, report, then ask before starting the next phase. Offer options; let the user pick when to cross into build. Relates to [[feedback-dont-reference-time]] — the user sets scope and sequence; I build to it, I don't set the pace.

Even after *extensive* design/mapping, the user may consider code FAR off — don't tee up "R0/build next" as the assumed step. On 2026-07-12, after a very thorough AdCP+AAMP surface-map (70 objects, 84+ gaps, all decisions), I framed "→ R0 next" and got: "we still aren't anywhere near ready to start writing code." There is substantial *how-to-build* design (module architecture, domain-model + execution/DBOS + protocol/transport/trust/settlement/console designs, conformance + sandbox harnesses, EXECUTION.md) between a complete surface map and code. Let the user declare when design is done.
