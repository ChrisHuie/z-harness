---
name: project-substrate-ownership-strategy
description: The strategic driver behind agentic-prebid — own the protocol-neutral substrate so no protocol/org controls Prebid
metadata: 
  node_type: memory
  type: project
  originSessionId: 1a4d69cf-6b26-472b-b224-242ef8a4868a
---

The `agentic-prebid` repo's real goal (kept OUT of committed docs by design — STATE.md marks
strategy/motivation as "private notes, intentionally NOT in this repo"): **Prebid controls its own
destiny by owning the protocol-neutral substrate that AAMP, AdCP, and any future protocol all reduce to**,
rather than being beholden to an external agentic-advertising governance org (the user's words: fight back
against "AAO"). The user is chuie@prebid.org.

The technical lever (as of 2026-07-09): whoever owns the canonical domain model owns AAMP↔AdCP interop,
because the two protocols have no direct lossless translation — both must project through a superset pivot.
Plus the operated rail (RFC 9421 identity, JCS signed receipts, dual-signed delivery oracle, settlement)
is greenfield in both protocols → ownable outright. Proof-in-code: `test_adcp_is_deletable`.

**Why:** wire protocols churn and can be captured by a governing body; the OpenRTB-family standards the
canonical model is anchored to (OpenRTB 2.6 / OpenDirect 2.1 / AdCOM 1.0 / Deal Sync 1.0 / Agentic
Audiences) do not.

**How to apply:** I authored `docs/SUBSTRATE.md` — the ownership map (Layers A–F: canonical model,
translation discipline, IAB-standards binding, two-axis dispatch, operated rail, neutral infra) that
re-organizes the six design briefs by "shared/ownable vs replaceable edge." Then `docs/PARITY.md` — the
parity ledger (5 fronts + scorecard) for making AAMP & AdCP equal peers. Keep the committed docs' framing
measured (say "a governance org," don't rant about AAO); keep the pointed political framing in
conversation/memory only. Repo is pre-implementation; next code step is Slice 0 (`src/core/trust/keys.py`
Ed25519).

**Key parity findings (2026-07-09 scan, in PARITY.md):** (1) THE META-FINDING — AAMP has no single
authoritative wire-contract artifact (only 5+ IAB object-specs that don't define wire/auth/error/
idempotency/discovery + a divergent, internally-inconsistent v0.1.0 impl). So making AAMP a peer requires
Prebid to AUTHOR/pin AAMP's missing wire contract — which is leverage (Prebid defines AAMP's real terms),
not just labor. (2) The canonical model is AdCP-leaning: it modeled the 6 AdCP↔AAMP collision concepts but
skipped AAMP-only machinery with no AdCP counterpart — curation/curator-fees (no home), agentic-audience
capability facts (CanonicalCapabilities is AdCP's cap-set minus envelope), buyer tier economics (only trust
ceiling survives; access_ceiling label-collision hides it → rename to trust_ceiling), negotiation engine,
change-request workflow. (3) AAMP-over-the-core is strictly BETTER than AAMP-native — it gains idempotency,
signed identity, and a creative-assign op AAMP lacks. (4) Brief corrections: quote≠get_products (it's a
TTL binding precursor w/ 409 conflict); order status polling-only (push_notifications:false); 3 error
shapes; openrtb_params never emits wadomain, at∈{1,3}. Briefs NOT yet patched — PARITY.md §6 wins on
conflict. (5) The non-parity trap: "AAMP-onto-AdCP-typed-kernel" (transport-coex §4) keeps AdCP privileged;
it's a temporary shim, real parity needs neutral kernel DTOs + unwelding SalesAgentBaseModel from
LibraryAdCPBaseModel.

**GATE A / MARKET REFRAME (2026-07-10, in `docs/POSITION.md`) — ground-truth corrected the earlier optimism.**
Ran Tracks 1–2 (drove real AdCP + AAMP agents locally; competitive-clock research). Key corrections & reframe:
- The interop-ownership SPINE holds, but the "own the uncontested operated rail/trust anchor as the moat"
  framing was WRONG. AdCP shipped RFC 9421 signing NORMATIVE (v3.1, Jun 2026), runs "AAO Verified" cert +
  `adagents.json`/`signing_keys`/`brand.json`; 8-vendor commercial agent-trust market (Forrester). Trust
  anchor is CONTESTED & consolidating to AdCP/AAO, locks ~AdCP 4.0 key-transparency (Q4'26–Q1'27). ~6–9mo.
- The GENUINELY OPEN seat = the **neutral cross-protocol bridge (AdCP↔AAMP lossless) + cross-protocol
  conformance**. Nobody's shipped it; only a neutral party can. THIS is the first flag, not the trust anchor.
  Track 1 proved surfaces are largely DISJOINT (AAMP 70 deal-centric REST endpoints vs AdCP ~15 media-buy/
  signals MCP tools) → bridge is necessary + unbuilt.
- BIGGEST FINDING: **Prebid is already being CAPTURED into the AdCP/AAO camp.** `prebid/salesagent` (this
  repo's base) IS AdCP's sell-side agent, transferred FROM AAO to Prebid Jan 2026; O'Kelley brands "Open
  Agentic Web, Powered by Prebid." AAO = AgenticAdvertising.org, Scope3-seeded (2/4 board Scope3+O'Kelley),
  "neutral in form, Scope3-driven in substance" — this is the user's "AAO." So peer-parity + `test_adcp_is_
  deletable` are the DE-CAPTURE mechanism (keep Prebid above both, not AdCP's distribution arm). De-capture
  is the point.
- Decision: push HIGH but REDIRECTED — bridge + conformance FIRST; operated rail = later differentiator
  (notary-not-bank, on the outside-adtech RFC9421/WebBotAuth/FIDO substrate). Clock ~2–3 quarters before
  AdCP 4.0 + AAO Verified-at-scale cement "AdCP = the neutral standard."
- The #1 unresolved unknown (per the intel brief) = Prebid's OWN intent: reclaim neutral-above-both vs accept
  the drift. That's the user's call; drift is the default. Recommended: reclaim, lead with the bridge.
- Reference agents run locally: AdCP hosted test agent is OAuth-gated (use local `hello_seller_adapter_*`
  examples, need `npm run build` first for dist/; CLI needs Node 22 for an ESM bug); AAMP seller-agent boots
  with `AD_SERVER_TYPE=csv` + dummy `ANTHROPIC_API_KEY` via uvicorn (captured its 70-endpoint openapi). Wire
  corpus in the session scratchpad/wire.
