---
name: reference-aamp-maturity-mid2026
description: "AAMP umbrella maturity map (mid-2026) — ratified at object layer, unspecified at agent-wire layer; which repos are spec vs code-only."
metadata: 
  node_type: memory
  type: reference
  originSessionId: 1a4d69cf-6b26-472b-b224-242ef8a4868a
---

**Expires:** when AAMP specifies or ratifies an agent-wire transport layer, or the umbrella
repo stops being README-only — re-verify against `IABTechLab/AAMP` before use.

Verified against live IABTechLab repos on 2026-07-10. The durable structural finding (SDK churn is transient; this split is the constant):

**AAMP = "Agentic Advertising Management Protocols"** (IAB umbrella, named Feb 2026). Three pillars: Execution (=ARTF), Protocols, Agent Registry. The umbrella repo `IABTechLab/AAMP` is a **README-only hub** — no spec, no umbrella version by design ("independent semantic versioning per repo"); omits deal-api/agentic-mobile; links ARTF by an old repo name.

Maturity by layer:
- **Object substrate = RATIFIED** and safe to bind to: OpenRTB 2.6, OpenDirect 2.1 FINAL, AdCOM 1.0 FINAL, Deal Sync API v1.0 (tag `1.0-202602`). Agentic Audiences = DRAFT (draft-2026-01, LiveRamp donation, no release tag).
- **Agent-wire layer = REFERENCE-CODE-ONLY, no ratified spec.** buyer-agent & seller-agent SDKs release-tagged `v2.0` (AAMP-2.0 branding) though `pyproject` still `0.1.0`; churn daily, still patching own semantics; diverge from each other (trust `TrustStatus`/`approved` vs `TrustLevel`/`verified`; state = 1 unified 12-state `OrderStatus` vs 4+ disjoint buyer enums; ≥3 error envelopes, producer defines none; **no idempotency key on the booking wire — buyer now blind-retries POST /quotes,/deals on 502/503/504 → dup-booking risk**; no durable cross-org webhook — only an in-memory dev event bus + MCP-transport SSE, not an AAMP push contract). `agentic-direct` is a separate stale TS A2A/MCP demo over OpenDirect.
- **Agent Registry = LIVE SERVICE, no ratified protocol** (only `POST /verify → {trust_level}`, defined by consumer/example code).
- **ARTF = DRAFT/public-comment** (v1.0 Nov 2025, comment closed Jan 2026, no FINAL). Only pillar with a real wire (gRPC/protobuf, Go+Rust), but **intra-host single trust domain** — a different layer than cross-org negotiation; its intents (`ACTIVATE_DEALS`/`ACTIVATE_SEGMENTS`) overlap the protocols pillar → watch the ARTF↔protocols seam.

Reframe (better than "AAMP has no wire"): AAMP **deliberately delegates the transport wire to MCP + Google A2A + REST/gRPC** and owns only the frozen-object semantics (the MCP-transport SSE above is the proof — streaming exists, but it's MCP's, not AAMP's). Strategic implication (reinforces [[project-substrate-ownership-strategy]], [[project-neutral-primitives-charter]]): **bind the canonical model to the frozen IAB specs, wrap the external transport SDKs, cite the AAMP SDKs as evidence only, never bind to their code.** The open seat = the neutral cross-org PRIMITIVE layer (idempotency, reliable delivery/webhooks, unified error, version-negotiation, receipts) — owned by nobody, unclosed through v2.0→3.0 — plus a conformance runner Prebid can own without forking. Full field inventory: `docs/design/aamp-substrate.md`.
