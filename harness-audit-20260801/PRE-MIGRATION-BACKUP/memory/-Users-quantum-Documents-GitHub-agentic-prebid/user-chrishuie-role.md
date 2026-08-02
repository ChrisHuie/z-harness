---
name: user-chrishuie-role
description: "Who ChrisHuie is: the person running the Prebid repos with deep AdCP + AAMP + ad-tech knowledge; NOT a commercial actor and NOT a Prebid officer (not President/Board). In our outputs, attribute governance/maintainership to 'Prebid', not to him personally."
metadata:
  node_type: memory
  type: user
  originSessionId: 1a4d69cf-6b26-472b-b224-242ef8a4868a
---

ChrisHuie (chuie@prebid.org) is **the person running the Prebid repos** (agentic-prebid, SalesAgent, agentic-advertising, and the other prebid-* repos) and a **deep domain expert** in AdCP — and now AAMP — plus other ad-tech. Stated 2026-07-13. He is:
- **NOT building a commercial product** — his role is technical stewardship, not commercial gain. Consistent with [[project-non-commercial-identity]] (Prebid authors open reference agents others commercialize; never operates a money-moving service for itself).
- **NOT a Prebid officer** — not President, not Board. He runs the repos; he does not hold org-political authority. Don't attribute org-leadership power to him.

**Substitution rule for our outputs (2026-07-13):** anywhere a doc/output would attribute maintainership or governance authority to "ChrisHuie" personally (e.g. `agentic-advertising/GOVERNANCE.md` literally says single-maintainer `@chrishuie`), **write "Prebid"** instead — the neutral non-commercial ORG is the authority, expressed through repo stewardship, not a named person's commercial or political power. (Do NOT rewrite the other repos' factual governance files; this is about how WE frame governance/authority in what we author in agentic-prebid.)

**Where "governance" actually lives (clarified 2026-07-13):** when the code needs a `governance` authority — the `AuthorityAssertion.source=governance` trust root, roster/verifier-selection decisions, `authored_by=governance` edges — and that authority is *Prebid*, it resolves to the **REAL Prebid organizational structure**: the current **Board + President** guidance, in partnership with the **PMC (Project Management Committee) chairs** who represent **publishers and ad-technology partners**. NOT ChrisHuie personally, NOT a code-invented body. And **Prebid does not add or operate new things** just because a design could use them — e.g. a Prebid-run verifier pool is **out of scope** ("don't know why Prebid would add or change anything it is currently doing"). The code owns the *mechanism*; governance *of that code* lives in the Prebid structure. Calibration signal: don't over-engineer speculative operational scope for Prebid ("this might be too in depth"). Reinforces [[project-neutral-primitives-charter]] (own the mechanism, never the authority) and [[project-non-commercial-identity]] (author-not-operate). Relates to [[user-plain-language-for-infra]].
