---
name: project-neutral-primitives-charter
description: "The 'own the mechanism, never the authority' 3-tier doctrine for agentic-prebid: which engineering primitives the neutral core owns vs conforms to vs co-governs — endorsed 2026-07-11"
metadata:
  node_type: memory
  type: project
  originSessionId: 1a4d69cf-6b26-472b-b224-242ef8a4868a
---

Endorsed 2026-07-11 (user: "think these 3 tiers are a good way to view this"). Triggered by the insight that idempotency is IN AdCP but the team built it into salesagent WITHOUT the AdCP SDK — because it's generic, testable engineering. Generalized (via a bottom-up engineering canon + a top-down AdCP/AAMP audit) into a charter for what the neutral core asserts control over while staying maximally neutral.

**The doctrine — "own the mechanism, never the authority."** Every capability splits into a coordination MECHANISM (testable pure function / state machine) and an AUTHORITY (trust root / identity / settlement). TEST: is it provable by a test that references no protocol's domain meaning and no party's trust relationship? → own it. If the test needs "party X is trusted" or "this is the authoritative money record," own the mechanism, keep the authority co-governed.

**Three tiers:**
- **T1 CONFORM (never own):** protocol semantics — what a media-buy IS, negotiation shape, audience/creative meaning, ARTF patch/intent taxonomy, state-machine VALUES. Owned by IAB/AAO.
- **T2 OWN (in the core):** neutral engineering primitives — idempotency + RFC-8785 canonical hashing (archetype), durable execution, **non-determinism quarantine** (the agentic-durability primitive nobody specified — flagship), exactly-once/outbox, saga/compensation, state-machine ENGINE (not values), error recovery-class {transient/correctable/terminal}, webhook/delivery engine, version negotiation, conformance harness + test-vectors, money-precision (Decimal/minor-units), concurrency/atomic-debit, TTL/deadline, translation-integrity (allow_lossy=False).
- **T3 OWN-MECHANISM-NOT-ROOT:** request signing/verify (RFC 9421 — verify+keyring, NOT the key authority/cert root), identity/registry (carry BOTH origin-auth adagents.json AND registry-auth IAB Agent Registry; never collapse), audit/receipts (hash-chained log + dual-signed oracle, NOT custodial settlement — "notary not bank"), HITL/spend-guardrails (mechanism not approval/cap-raise authority).

**Why it stays neutral (key finding):** the cross-org primitive layer is UNCLAIMED across all three surfaces — AdCP specifies these well but doesn't force its SDK; AAMP barely specifies; ARTF punts by design (single trust domain, no external egress). Owning T2 the right way makes us MORE neutral (both protocols benefit equally, no SDK lock-in) and IS the embeddable-primitive play that makes us the default substrate.

**Grab first (highest leverage):** (1) **idempotency vs canonicalizer — DON'T conflate** (refined w/ user 2026-07-11): (a) IDEMPOTENCY = SIMPLE (a client idempotency-key + "seen this key?"); the salesagent implemented it separate from the SDK as a natural key (`buyer_ref`) + DB check-if-exists — "not much more to it"; harvest the CONCEPT + formalize the key ONTO the wire (AAMP has none → that IS the dup-booking fix). (b) RFC-8785 CANONICAL HASHING = a SEPARATE primitive that does NOT exist in the salesagent → BUILD FRESH, justified by RECEIPTS + SIGNING (canonical deterministic bytes to hash-chain + RFC-9421-sign receipts / cards / mandates — "same hash = keystone of receipts"), NOT primarily idempotency (only a secondary same-key-different-body defense); (2) protocol-neutral conformance harness (defines the bar both protocols must pass — soft power); (3) webhook + error-recovery-class engine (AAMP is polling-only w/ 3 error shapes → own it and AAMP-over-core is STRICTLY BETTER than AAMP-native = "completes the protocol," a neutral adoption lever).

**Tier-3 traps to avoid:** don't become the signing-key/cert authority; don't collapse origin↔registry trust roots; don't run custodial settlement. Root of trust stays OUTSIDE Prebid (RFC 9421 / FIDO / IAB registry / AAO); Prebid owns the neutral verification over them.

Full charter: coverage-map.html §08 + scratchpad/primitives-charter.md. Equips the substrate in [[project-positioning-and-core-decisions]]; serves [[project-substrate-ownership-strategy]].
