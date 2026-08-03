---
name: feedback_primary_sources_over_press_coverage
description: "External systems/specs must be researched from primary sources and installed artifacts — press coverage and vendor blogs are leads, never evidence"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 3212cffc-7f9f-49b3-8607-75da70ef8eb1
  modified: 2026-08-01T16:54:07.113Z
---

When answering about an **external** system (a spec, a protocol, a competitor's
implementation, a standards body's framework), a WebSearch summary, press release, vendor
blog, or aggregator article is a **lead to a primary source, never the evidence itself**.
Primary sources, in priority order:

1. **Locally installed artifacts** — introspect the actual package in site-packages, read
   the actual source, run the actual import. If the SDK is installed, that is ground truth
   and it must be checked BEFORE reading anything about it.
2. **The spec repository** — schema files, `.proto` files, normative documents, CHANGELOG.
   Distinguish MUST/SHALL from SHOULD/MAY for every security-relevant claim.
3. **The implementation's source code** — not its README, not its GitHub landing page.
4. Only then: analyst and vendor writeups, and only to find (1)–(3).

**Why:** three consecutive rounds of a high-stakes architecture plan were built on press
summaries. Each time the user pushed back, the primary source materially changed the
conclusion — an implementation dismissed on marketing turned out to have a real security
model; a framework characterized as dangerous turned out to be conventional ML with a
sound broker pattern; a claimed protocol gap was never checked against an SDK sitting
installed in the venv. Secondary sources compress away exactly the normative/advisory
distinction, the unspecified gaps, and the second-order interactions that the analysis
depends on. Plans are upstream of everything; a shallow plan poisons all downstream work.

**How to apply:** before asserting anything about an external system, ask "what is the
primary artifact and have I opened it?" If resources are available (tokens, time,
subagents) **depth is the default, not the escalation** — fan out one agent per
load-bearing claim, each instructed to cite exact file:line or URL+section+quote, to
report CONFIRMED / REFUTED / CANNOT VERIFY, and to state gaps rather than fill them with
plausible inference. Explicitly hunt second- and third-order interactions between systems,
not just first-order facts about each. Never let a claim become load-bearing in a plan
without a primary citation attached to it. See [[verify_before_asserting]],
[[trace_flows_not_claims]], [[thoroughness_over_momentum]],
[[no_agent_fanout_by_default]], [[adcp_spec_grounding]].
