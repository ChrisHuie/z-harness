# Deferred rules — displaced from the body by the 5,000 B cap

Every rule here is rank A or B and survived the substitution test (true and useful in a repo
you have never seen). They are out of the body because 23 slots exist and the block is
larger. Load this file when the design touches the topic in the section heading.

Rank: **A** = violating it ships a system that is wrong in a way nothing will catch —
an unrevokable authority, an irreversible wrong effect, a guarantee that was never there.
**B** = wastes work or produces a weaker system without asserting something false.

Six headings are name-cited from the body and marked `[body]`; the other six are reachable
only from this file's own table of contents.

---

## Authority and signed evidence `[body]`

- **A** **No domain separator inside the signed bytes ⇒ the signature is re-aimable** at a
  different consumer. Bind the audience into what is signed, not into the envelope.
- **A** **"Ours" is not "bankable ahead of the chain"** — a mechanism you own can still be
  unenforceable because its inputs are not plumbed to it. Trace each input to its producer
  before counting the guarantee.
- **A** **Assurance is attribution, not truth.** An assurance level says who stood behind the
  claim, never that the claim holds.
- **B** **Reject a credential/signature format whose only production-grade library lives in
  another runtime** — pick what your runtime verifies natively; a shell-out to verify is an
  unbounded dependency inside your trust computation.
- **A** **A self-reported marker cannot bound an adversary who controls it** — attribute any
  bound to the independent mechanism that produced it, never to the tag.
- **B** **Make a witness's fee volume-independent if it also witnesses the volume**, or the
  witness is paid by the number it attests.
- **A** **A ceiling without a floor is half an authority model** — bound one direction, then
  ask for the dual. *(Demoted from the body 2026-08-02 to make room for R172, the trust-anchor
  rule, which had no home in any body. Its sibling clause — a safety property scoped to one
  path leaves every other path unprotected — stayed in the body under Irreversible effects.)*

## Containment and adversaries

- **A** **Ship a bounded guarantee with named residuals, never "airtight"** — state what is
  out of scope instead of assuming it away. A guarantee with no residual list has not been
  scoped.
- **A** **A human-in-the-loop gate is model-steerable by persuasion** whenever the model
  authors the rationale the human reads. An exfiltration scan does not catch persuasion; the
  countermeasure is evidence the human can check without the model's framing.
- **A** **Two adjacent components can each assume the other gated a check.** For every
  cross-component invariant, name the single component that owns it.
- **A** **Default to a boundary-respecting mock** — the fake sits *across* the real trust
  boundary. An in-process fake proves nothing about the boundary it replaces.
- Already homed elsewhere, do not restate here: *the synthesizer cannot red-team their own
  synthesis* lives in the `agent-dispatch` body. **R172 — a trust anchor the constrained thing
  can write is not a boundary — is now in THIS skill's body** under Containment; it was in no
  body at all until 2026-08-02, because this file deferred it to `agent-dispatch` and
  `agent-dispatch` displaced it back here as design-time work.

## Deferred actions, transitions, cascades

- **A** **A durably-committed transition atomically enqueues its reactions in the same
  transaction** — at-least-once delivery made idempotent by (causing sequence number,
  ordinal). Enqueue outside the transaction and the reaction is lost on rollback.
- **A** **Record the author on every transition and declare a closed authorship policy per
  edge** — no party unilaterally moves a shared record to its own benefit.
- **A** **A strictly-backward causal reference makes the causality graph acyclic BY
  CONSTRUCTION** — cheaper than cycle detection and it cannot be bypassed.
- **A** **Cascade safety = acyclic-by-construction + a closed finite catalog with static
  depth and fan-out bounds + one choke point + idempotent effects.** A cascade only PROPOSES;
  the guard DISPOSES.
- **B** **A singleton where the domain has N is a cardinality bug**, not a simplification.

## Two-party and reconciliation designs

- **A** **Two parties measuring DIFFERENT events need a structural tolerance band** — the gap
  is systematic, not noise. Without the band you get spurious disputes or hidden fraud.
- **A** **An exposure fold must be TOTAL** so it can never release un-reversed spend.
- **A** **A stored earmark alongside a derivable fold is a second source of truth** — drop
  the stored object, keep the fold term.
- **A** **A cross-aggregate invariant needs a real mutex, not an optimistic fence.**
- **B** **When two designs collide, look for the orthogonal axes that make them
  non-competing** — they often compose as a conjunction at the commit edge.
- **B** **Two grains that cannot be joined** (per-run vs per-day aggregate) reconcile at the
  grain boundary with an explicit tolerance; make "spend joined to no run" a first-class
  alerted metric rather than a silent residue.

## Dependencies, vendors, supply chain `[body]`

- **A** **Mitigate vendor risk by design, not by vendor health** — a permissive licence plus
  state as ordinary tables in your own store means their failure costs future development,
  not your running system or its data.
- **A** **Vendor a thin single-maintainer library on the critical path behind your own thin
  implementation**; pin and wrap a package with no release in a year or with issues disabled.
- **A** **Keep the type-gate on a checker not owned by the same vendor as the rest of the
  toolchain** — a single vendor owning both the toolchain and its checker removes the
  independent reading.
- **A** **A hosted model has no reproducibility guarantee**, which upgrades record-and-replay
  from prudent to necessary.
- **B** **Record provider-specific sampling parameters as a provider-tagged union** — one
  provider rejects another's fields.
- **B** **Every new side-effecting port must be registered in the replay/shadow set**, or
  replay becomes a live action.
- **B** **Origin is not control** — vendor-originated but now neutrally governed is a
  different risk class from vendor-controlled.
- **B** **No single external standard is load-bearing** — keep plural, bind the
  transport-neutral core rather than vendor extensions, treat unratified bodies as
  watch-and-align, not depend.
- **B** **Prefer catalysing a multi-party arrangement under an existing neutral body over
  doing it solo** — solo hands critics the symmetry argument.
- **B** **Buy portability, not multi-cloud.**

## Unbundling a gatekeeper

- **A** **Unbundle what a single gatekeeping service bundles**: identity at the party's own
  domain, capability self-published, findability via plural indexes, authority as a signed
  mandate checked against an open root, trust as portable attestations. **Being in a registry
  is not a trust signal.**
- **B** **Maintain the PORT and your own adapters; third parties write theirs** — adopting a
  fleet of third-party adapters is the maintenance trap.
- **B** **Anchor a canonical model to the slow-moving standards, not the churning wire
  protocols.**
- **B** **When two formats have no lossless translation, both project through a superset
  pivot — whoever owns the pivot owns the interop.**
- **B** **"No single authoritative wire-contract artifact" means adopting it requires you to
  AUTHOR the contract** — that is leverage, not just labour.
- **B** **Run the ground-truth pass before committing to a strategy** — the reality check is
  what corrects an optimistic read of who already occupies the position.

## Protocol and transport seams

- **A** **Design against a protocol's ANNOUNCED direction, not just its current version** —
  when a release candidate removes a construct, do not depend on it now.
- **A** **A seam over multiple transports MUST abstract push-native vs poll-native** — that
  difference does not vanish behind a common interface.
- **B** **Identify what a protocol PUNTS and own that layer** — completing its mechanism
  layer is not competing with it.
- **B** **Confirm wire-string literals byte-level against the schema before hardcoding** —
  abstract names differ from wire method strings.
- **B** **A directional primitive is not a symmetric peer volley** — model the asymmetry.

## Typed boundaries and errors `[body]`

- **A** **Split exception migration by AUDIENCE** — an error that can escape to an external
  caller becomes a typed, wire-shaped error; a programmer-contract violation stays an untyped
  crash, because wire-shaping it misreports a code bug as a caller fault. The discriminator
  is the call graph: can this raise reach the boundary with no intervening handler?
- **A** **Put a catch-all translator at the boundary** so a misclassification degrades rather
  than crashes.
- **A** **An object obtained inside a managed scope** (transaction, session, context manager,
  pool checkout, temp dir) **may become invalid at scope exit LAZILY** — the failure appears
  at the first attribute access *outside*, not at exit. Keep reads inside the scope or copy
  the scalars out.
- **A** **Two-mechanism versioning**: an extra-fields mode handles forward-compat junk;
  declared-deprecated fields plus pre-validators handle version *translation*. Conflating
  them fails one of the two jobs.
- **B** **Environment-driven strictness** — forbid-extras in dev, ignore in prod.
- **B** **A serializer wired once at the engine level beats per-call serialization.**

## Config as policy `[body]`

- **A** **Everything that is POLICY becomes schema-validated CONFIG; the mechanism enforces
  the config.** Layer it (defaults → deployment → tenant → per-request) with explicit
  precedence.
- **A** **Strong defaults — configuring nothing must give a working system.**
- **A** **Do not expose every internal as a knob, only genuine policy decisions.** That
  clause is what prevents config sprawl; without it, layering makes it worse.
- **A** **Never let a foreign system's identifier be your primary key** — mint your own
  durable identity and keep the external id as a foreign key inside the adapter. Crossing
  that line welds you to the external system.

## Migration sequencing

- **A** **A paused programme records its resume preconditions** — verify branch currency and
  whether the approach shifted while paused, before restarting.
- **A** **A lazy-evaluation hazard reproduces only on the path production takes** — a
  test-path/prod-path accessor divergence hides it entirely.
- **B** **Port the behavioural specs as the acceptance layer** when greenfielding a spine;
  drop everything that is neither spine nor edge-case-dense.
- **B** **When a change makes a standing decision's wording false, amend the decision row** —
  otherwise the spirit survives and the letter misleads. Flag immutable-once-set parameters
  at the point of setting.
- **A** **Copy edge-case-dense modules verbatim with their tests; never rewrite one from its
  contract tests** — contract tests under-specify the internal rules. *(Demoted from the body
  2026-08-02 to make room for R172.)*

## Human-facing surface `[body]`

- **B** **The surface is a typed API, not a UI** — the frontend is pluggable and
  non-load-bearing, so testability is headless request/response asserts with no browser, and
  a bring-your-own frontend tests against a mock of the contract.
- **B** **Render NEUTRAL domain objects, never the upstream payload** — the source format is
  a labelled attribute plus a raw drill-down, never the STRUCTURE of a screen, or you build
  one console per source.
- **B** **Render errors as ACTIONS by recovery class** — correctable → fix the field;
  transient → retry ETA; terminal → why plus a receipt.
- **B** **Testable BECAUSE the queue IS the durable workflow** — state in an in-process
  thread plus a module global is dropped by a restart and cannot be durably tested.

## Fleet and tooling architecture `[body]`

- **A** **Substitution map**: classify every dependency swappable-by-design (substitute
  named, seam thin, exit REHEARSABLE) or deliberately-coupled (conscious bet, documented
  exit, trigger). **Unclassified is an audit finding.**
- **A** **Relocating one component is availability THEATER when the actual gate lives
  elsewhere** — the unit of analysis is the whole control path.
- **A** **Separate first-pass validity from post-repair validity**, or the repair step
  launders the weakness it is repairing.
- **B** **A hermetic renderer is a pure function of (tree, target) → artifacts + manifest** —
  no timestamps, no env inputs, so the same tree yields the same hash. That property is what
  makes one-variable experiments and incident attribution real. Lint INSIDE the render,
  unskippable.
- **B** **Per-field provenance**: `value + source + is_estimate + candidates`, so
  disagreement between sources is visible as data rather than resolved silently.
- **B** **Cost derived from a hardcoded price table discards the authoritative reported
  total** — carry the reported figure and treat the derivation as a cross-check.
- **B** **Choose a CI-distributed tool's implementation language for its DISTRIBUTION
  properties** (single static binary, zero runtime deps in every consumer's CI), not for the
  ecosystem of its data. Keep per-language pieces in their language; the tool consumes only
  their JSON and never imports another language's SDK.
- **B** **Tier options by the ACTUAL isolation boundary and LABEL the tier** rather than
  treating them as interchangeable.
- **B** **Open-sourcing an isolation primitive is a strength; only the deployment stays
  private.** A vendor closing source is a commercial moat, not a security truth.
- **B** **Neutral governance is the decisive tie-breaker between otherwise-equivalent open
  dependencies.**
- **B** **Ramp with capability** — cheap load-bearing controls now, heavy infrastructure once
  authority and evidence earn it.
- **B** **"Inherited-solved": name the risks your operating context already covers and stop
  re-raising them**; spend the risk budget on the genuinely novel adversarial surface.
