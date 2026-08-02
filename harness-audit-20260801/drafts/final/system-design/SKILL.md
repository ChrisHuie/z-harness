---
name: system-design
description: Design-time rules for systems where trust boundaries, irreversible effects, or a party you do not control are load-bearing. Use when threat-modelling, deciding who may assert or approve what, designing containment for autonomous components, judging whether a seam really makes a dependency swappable or a vendor replaceable, or sequencing a migration cutover.
---

# System design

**If the design turns on typed boundaries and errors, config as policy, or any topic below
that this body does not already answer — Read `references/deferred.md` first.** It holds 72
further rank-A rules; this body holds 23.

## What you may own

- **Split every capability into a coordination MECHANISM and an AUTHORITY** (trust root,
  identity, money); own the mechanism, never the authority. **Test: provable by a test that
  references no domain meaning and no party's trust relationship?** If it needs "X is
  trusted", it is authority — externalize it.
- **Own the keyring never the keys, the verifier never the root**, and never merge two
  distinct trust roots. Emit a source × assurance **set**, never a scalar — collapsing to a
  score is the act that makes you the authority.

## Who may assert what

- **A predicate resolves the specific controller × scope × fact-type, not the kind** —
  pinning a kind collapses the gate to one spoofable bit.
- **A feature's headline capability is its attack surface** — "trust many issuers" means any
  trusted issuer can forge for anyone.
- **Self-issuance collapse** — where issuer and subject can be one key the assertion is
  self-asserted, not witnessed; the issuer must be provably disjoint from the delegated keys.
- **Monotonicity checks are direction-blind** — a subset test inverts wherever narrower means
  *more* permission (an emptied exclusion list now targets the excluded). Encode it per field.
- **A role or tenant is a filter derived from the authenticated principal, never a request
  field**, and it narrows, never widens, the policy.

## Independence

- **Independence must be economic, not cryptographic** — key disjointness does not give the
  interest-independence corroboration needs, because whoever **selects and pays** a party
  aligns its interest. Two sources check each other only when their interests oppose.
- **Test disjointness over the union of witnesses AND fee beneficiaries** — a shell passes
  "not self" because its key is not the party's. Record who funded and selected each
  attestation.
- **Act only on ≥2 independently-sourced facts, no single-source fallback** — the fallback
  silently defeats it, and a re-signed reading is two roots, one observation.

## Containment

- **A threat model here states what holds no matter what the components do**, not attacks at
  a perimeter — the dangerous actor is inside, authorized, autonomous, and indistinguishable
  from an honest one. **State the adversary once as a capability set** that every component,
  yours included, may exhibit.
- **Components PROPOSE, the kernel DISPOSES** — gate on witnessed facts, never authored
  state. **"X happened" is not "X was authorized."**
- **Seam-by-seam verification is blind to cross-seam composition** — every hop passes its
  local guard and the chain is still catastrophic. **Sequential quorums compose as `min`, not
  sum**: the second corroborates a different proposition.
- **A trust anchor the constrained thing can WRITE is not a boundary** — receipts, tiers,
  hook scripts, an "append-only" ledger and settings are all plain text its subject edits.

## Irreversible effects

- **A safety check's failure mode is HALT, not continue.**
- **Compensate forward** — an effect on someone else's system cannot be un-done, so a
  reversal is a NEW obligation, never an edit to the old record.
- **The core never self-advances a positive irreversible fact** — those transitions are
  ingress-only, gated on cross-boundary signed evidence.
- **Guards evaluated at enqueue and re-checked only for legality at drain are a TOCTOU** —
  re-evaluate the FULL precondition at the commit fence. **An approval bound to an ID, not a
  content digest, permits a post-approval swap.**
- **A safety property scoped to one path leaves every other path unprotected.**

## Seams and dependencies

- **A "swap X behind a thin seam" escape hatch can be semantically illusory — the seam ports
  the interface, not the guarantees**: same-transaction exactly-once is a property of the
  co-located store. Check the alternative delivers the property first.
- **Usage may grow but import sites may not**, and the dependency stays in the decision
  layer, never in mechanism. **Prove removability with a test that runs the flow with the
  package un-importable** — a seam is not proof of separability.

## Boundaries and cutover

- **One typed internal representation; serialize only at system boundaries, once in and once
  out — never between internal layers**, errors included: an untyped dict boundary matches
  nothing silently and runs on empty parameters.
- **Freeze the external contract and lock it with protective tests before layer 0** —
  internal breakage is free while that surface holds. Introduce the indirection early so the
  semantic cutover is a one-line alias flip late; give each layer a machine-checkable exit
  gate.
