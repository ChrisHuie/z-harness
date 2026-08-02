---
name: project-configuration-first
description: "Configuration-first design principle for agentic-prebid: the open-source agents/runtime are a configurable ENGINE (Prebid.js setConfig DNA) — everything-that's-policy is CONFIG not code; schema-validated (pydantic), layered, modular, strong-defaults; the adoption/democratize + neutrality mechanism at the code level"
metadata:
  node_type: memory
  type: project
  originSessionId: 1a4d69cf-6b26-472b-b224-242ef8a4868a
---

Locked 2026-07-11 (user: "have we thought like other Prebid products about configuration that makes the open source agents even more flexible for the users"). Core Prebid DNA we'd been applying piecemeal (D2 "publisher-tunable"; pydantic config-for-free) but hadn't elevated to first-class.

**THE PRINCIPLE: the open-source agents + runtime are a configurable ENGINE, not opinionated code.** Prebid.js won by being configuration-driven (`pbjs.setConfig`, modules, per-adapter params) — you don't FORK it, you CONFIGURE it. Same here: the agent LOGIC is generic; CONFIG specializes it per user/publisher. **Everything-that's-policy is CONFIG, not code** — the clean generalization of "own the mechanism, leave the policy configurable."

**It dissolves the runtime policy decisions (D2–D5) at once — they're all "make it a knob":** hold TTL/soft-hard, HITL escalation thresholds, warm-vs-resume, buyer fan-out strategy, enabled protocols (A2A/MCP/REST), enabled BookingSinks, required certifiers (the "header bidding for compliance" matrix — e.g. "I require IAB+Prebid"), accepted mandates/counterparties, negotiation strategy limits, brand-safety, model choice. Config sits at the POLICY layer: it PARAMETERIZES the deterministic Gate/Commit — the mechanism enforces the config; the model decides within config-defined guardrails.

**Why it's load-bearing (not just convenient):** (1) ADOPTION/democratize — configure-not-fork is THE low barrier (how Prebid.js reached the long tail); (2) NEUTRALITY — we ship neutral mechanism + knobs, each user sets their own policy/worldview = the anti-app-store ("configure to your needs," NOT "comply with our storyboards"); we hand over the dials instead of imposing opinions; (3) FLEXIBILITY/serve-anyone at the code level. This is the CODE-LEVEL expression of [[project-non-commercial-identity]] (we don't operate or opine — we hand over a neutral configurable engine and get out of the way).

**Do it right (learn from Prebid.js's config sprawl):** schema-VALIDATED (pydantic — typed, JSON-schema, self-documenting; no parse-and-hope; the schema IS the docs) · LAYERED (defaults → deployment → tenant → per-request, clear precedence; per-tenant ties to runtime D1 isolation) · MODULAR (enable/disable capabilities like Prebid.js modules) · declarative + hot-reloadable where sensible · STRONG DEFAULTS — the discipline that keeps config from becoming the Prebid.js firehose: configure-NOTHING gives a working agent; deep config is there when needed, not required to start. Don't expose every internal as a knob — only genuine policy decisions. Democratize = easy default + deep-when-needed.

[[project-positioning-and-core-decisions]] [[project-neutral-primitives-charter]] [[project-agent-trust-layer]]
