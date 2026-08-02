---
name: project-aamp-play
description: "AAMP strategy for agentic-prebid: 'complete not host' — author the mechanism layer, bind to frozen IAB objects, build INDEPENDENT of the slow IAB working group. Decided 2026-07-11."
metadata:
  node_type: memory
  type: project
  originSessionId: 1a4d69cf-6b26-472b-b224-242ef8a4868a
---

Synthesized 2026-07-11 from a 4-stream AAMP deep-dive (maturity, implementation, IAB-relationship, governance-threat).

**The play — "we don't host AAMP, we complete it."** AAMP is mature at the frozen OBJECT layer (OpenRTB / OpenDirect 2.1 / AdCOM / Deal-Sync — bind to these) but reference-code-only at the AGENT-WIRE layer, which is self-contradictory (its own buyer & seller SDKs disagree on trust vocab, share no state machine, ship 3 error shapes; no ratified agent-to-agent wire). Author the neutral MECHANISM layer IAB left undefined (idempotency, push, versioning, error-recovery-class, conformance); bind every SEMANTIC to the frozen objects (SDK = evidence-only + a divergence ledger); never author AAMP semantics. Additive-and-ignorable shims (strip extensions → valid AAMP-native, guard-tested) → "AAMP-on-our-core strictly better than AAMP-native" is arithmetic.

**Three layers, three owners:** semantic objects = IAB Tech Lab (conform); transport wire = Anthropic MCP / Google A2A / gRPC (wrap, don't reimplement); the neutral cross-org primitive+wire layer = unclaimed = ours. NOTE: AAMP 3.0 is real (~July 2026) but BREADTH not durability — it closes none of our 4 primitive gaps and none of it is in the reference repos yet; ARTF v2.0 unratified. The primitive layer is provably unclosed through 2.0→3.0.

**Recognition [USER-DECIDED]: build INDEPENDENT** (Apache-2.0, Prebid, ship at code-speed) — NOT inside the IAB working group ("we will work with them but they are too slow"). Work-with = conform loudly + feed conformance fixes back + list in the registry; the build and timeline stay ours. Overrules the research's "co-develop inside the WG before shipping" rec (imports committee latency).

**Why control is REAL (guard tests, not claims):** we can grade an AAMP agent against AAMP's own frozen specs and its reference seller-agent FAILS them (we can test AAMP; AAMP can't test itself); crash-safe exactly-once vs AAMP's ambiguous "already booked" race; lossless AAMP↔AdCP round-trip (allow_lossy=False) — a seat only a neutral party can hold.

**Defense = the single-camp lock:** a single-camp, anti-AdCP body can't author a neutral bridge or grade both sides; cross-protocol interop + conformance belongs only to a neither-camp party backed by a constituency — Prebid's publisher mandate (proven in the Aug-2025 TID win, which Prebid WON; that fight was really a Trade Desk attempt to weaponize the spec — see [[project-positioning-and-core-decisions]]).

**Watch-items (none landed):** SDK soft-power trap (SDKs relabeled "production-ready" to become de-facto contract → bind to spec, keep divergence ledger); ARTF scope-creep into deal activation; IAB registry "ads.txt-for-agents" graduating into a signed-identity wire (would be worth binding to). Runway ~2-3 quarters.

Maturity detail: [[reference-aamp-maturity-mid2026]]. Serves [[project-substrate-ownership-strategy]]; applies [[project-neutral-primitives-charter]].
