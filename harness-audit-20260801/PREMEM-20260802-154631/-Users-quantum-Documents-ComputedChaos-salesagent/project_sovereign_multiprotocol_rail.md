---
name: project_sovereign_multiprotocol_rail
description: "Initiative to make the Prebid Sales Agent a sovereign multi-protocol rail (AdCP+AAMP+native, AdCP deletable); where the specs live and how to resume."
metadata: 
  node_type: memory
  type: project
  originSessionId: 57dfb91a-b17e-4cf1-92a7-b9a49e533e36
---

Initiative (started 2026-07-08): make the Prebid Sales Agent speak AdCP **and** AAMP **and** a Prebid-native protocol over any transport, own a canonical domain model neither protocol body controls, and make the AdCP surface a **deletable edge module**. Driver: keep Prebid from being governed by AAO/Scope3 via AdCP. Ground work, do not re-derive.

**Where the work lives:**
- **NEW REPO (the build target, decided 2026-07-09): `github.com/ChrisHuie/agentic-prebid`** (PRIVATE, Apache-2.0). Cloned locally at `/Users/quantum/Documents/ComputedChaos/agentic-prebid`. The **technical** context is committed here (or staged to be): `docs/STATE.md` (START HERE), `docs/ARCHITECTURE.md`, `docs/BUILD-PLAN.md`, `docs/design/*.md` (the 6 briefs, copied clean). From a cold start: memory → this repo → `docs/STATE.md`.
- **Private strategy/motivation (intentionally NOT in the repo):** `.claude/notes/sovereign-rail-build-spec.md` (strategic-framed original, has the AAO/Scope3 "why") + `.claude/notes/deep/*.md` (originals) in the salesagent working dir — UNTRACKED, local to this machine. The repo docs are the neutralized technical versions.
- Committed repo docs are STRICTLY technical (protocol-independence framing); the competitive "why" stays in private notes + this memory only.
- A stale claude.ai Artifact ("Sovereign Operated-Rail" review) reflects the OLD skeleton — refresh or ignore.

**Research: COMPLETE** (6 lanes, all vetted against code). Key verified facts: domain model FUSED to AdCP (48 classes subclass `Library*`, `_base.py:232`); repo abstracts TRANSPORT not PROTOCOL (`resolved_identity.py:35`); AAMP's stable anchor is the frozen IAB substrate (OpenRTB 2.6 / OpenDirect 2.1 / Deal Sync v1.0 / AdCOM) — its v0.1.0 agent impl DIVERGES from spec, bind to spec; AdCP is a LOSSY projection of our own error taxonomy (`exceptions.py:48-50`); PSA + AAMP both build GAM via the same `LineItemService.createLineItems` (GAM adapter = 10k LOC); AdCP has ZERO deal-mechanic fields (introspection-verified).

**Sovereignty = two milestones:** A = multilingual + native ({protocol}×{transport} adapters, `_impl` unchanged, near-identity); B = unweld the 48 `Library*` subclasses → `test_adcp_is_deletable` goes green.

**Decision (made 2026-07-09): CLEAN-REPO rewrite in `agentic-prebid`**, because salesagent is open-source (Apache-2.0) + behavioral tests are portable. Phase = pre-implementation (docs done, no product code yet; next = Slice 0 trust/keys+keyring). Discipline agreed: **greenfield the spine** (`domain/`,`protocols/`,`transports/`,`trust/`,`settlement/`); **COPY (don't rewrite) edge-case-dense modules** (GAM, pricing-compat, idempotency canonicalizer, targeting) — verbatim + their tests; **PORT the behavioral specs** (37 BDD `.feature` + ~54 wire-contract files) as the acceptance layer; **drop** Flask admin (~24k LOC, already migrating), the 48 AdCP-welded schemas, 271 impl-coupled unit tests, 73 old structure guards. The line held: do NOT rewrite the edge-case core from the contract tests alone — they under-specify the ~thousand internal business rules.

**Open items / next-step candidates:** (1) the module-by-module **copy/greenfield/drop manifest** (offered, not yet built — the buildable rewrite plan); (2) 8 Prebid decisions in spec §10 (load-bearing: state authority, trust-root downgrade→recommend always-raise, PG line-item type); (3) FastMCP schema-from-signature is the prototype-FIRST risk (`main.py:305`); (4) Slice 0 = asymmetric signing + keyring.

**How to apply:** on resume, READ the spec file first (it's the index). Re-verify any file:line before acting — code may have moved. Related: [[user_profile]], [[feedback_no_agent_fanout_by_default]] (this used an authorized go-wide 6-lane fan-out), [[feedback_ground_protocol_work_in_spec_not_assumptions]].
