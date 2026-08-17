# Deferred rules — displaced from `SKILL.md` by the 5,000 B body cap

31 rank-A rules (violating one ships a false green or a false finding) plus 13 rank-B/C rules,
kept here because the body could not hold them without stripping the mechanism from a rule it
already carries. Registry ids are `PRINCIPLE-REGISTRY.md` §3 row numbers.

Read this file when the body's rule fired and did not resolve the case, or when the work is in
one of the sections below. All seven headings are name-cited from the body; they are marked
`[body]` so the pointer and the heading are checkably the same string.

## Environment and contention `[body]`

- **R105** Failures clustered in resource-heavy tests that **do not reproduce in isolation** are
  the contention signature of a shared single-instance resource. Prove it with a clean
  serialized re-run; never conclude "flaky" or "infra" by assertion.
- **R106** A green run against a **persistent, never-torn-down fixture** is necessary and never
  sufficient — a long-lived datastore accumulates every migration ever applied, converting a
  provisioning bug into a false green. Re-run against a from-scratch instance.
- **R103** A package manager trusting its own **metadata** reports "in sync" over a corrupted
  environment. An import failure with the package listed installed is a corrupted env, not a
  lock or code problem; a type-only dependency going unimportable surfaces as a spurious
  "unused ignore".
- **R102** A hook running in an **isolated environment with its own dependency declaration**
  emits phantom errors when its pin drifts from the runtime pin. Pin exactly to the runtime,
  bump both in the same change, clear the cache.
- **R124** (B) A **runner artifact is not a regression** — a containerized runner sees a build
  context stripped by the ignore file, so tests scanning excluded paths fail inside and pass on
  the host. Keep a known-artifact set; prove branch-independence by **both** provenance and
  environment-specificity.
- **R134** (B) Under a parallel runner, **hardcoded resource IDs collide**. Allocate unique
  per-test IDs.
- **R138** (B) Run workspace suites **from their own directory** — a root-flag invocation
  misresolves paths and fakes failures.

## Runner and CI verdicts `[body]`

- **R104** When CI fails **twice on the same target with a different error each time**, you are
  peeling layers of rot. Stop pushing speculative fixes and reproduce locally against the full
  stack.
- **R108** The **convenience quality target is a subset of the suite**. A whole-tree invariant
  check means a one-file edit can fail an unrelated file, so per-file selection structurally
  cannot catch it; **CI is not a superset of local**; a lower collected count offline is the
  tell.
- **R125** A **scanner's tooling crash is not a finding** — re-run before owning it. A scanner
  reporting "not scanned" is not reporting "zero findings": a tool's no-op mode reads as a
  clean result.
- **R115** Gate logic inside a **CI config heredoc is untestable by construction** — extraction
  is the prerequisite for coverage, so "add tests" is the wrong ask. Keep pipeline logic in
  repo scripts with the CI YAML as a thin trigger adapter.
- **R116** Duplication and quality ratchets scan only **source scopes**. Copy-paste inside CI
  config, and inside new test code, is invisible to them — worst on a security gate with two
  hand-synced verifiers.
- **R100** A conditionally-gated optimization silently **no-ops through a working fallback**
  while everything stays green. Verify it *engaged* from the runtime log's per-branch marker;
  then **engagement ≠ benefit** — measure wall-clock against the no-optimization baseline.

## Vacuous and self-clearing detectors `[body]`

- **R109** A detector's documented **remedy can clear the detection**. Run the remedy before
  declaring a mutation survivor, and score raw vs semantic kills separately.
- **R110** A check pinned to a **path goes vacuous when content moves**, with no signal —
  coverage fell 60/60 → 1/60 while the checker reported "clean, 219 items" over a tree with 157
  emptied.
- **R099** A **coherence checker** validates a pairing against a table and cannot see whether
  the pair fits the actual condition — a clean run means coherent, not correct.
- **R112** A **keyword detector on self-reported language measures claims, not outcomes** (fired
  on 83.5% of bodies, wrong about the majority, 59.3% of the language written by the claimant).
  A self-reported count is gameable by reclassification — check the classification rule, not
  the count.
- **R111** A gate depending on a **number** needs the landed script, exact tree, seed, output
  and hash. The author's own re-derived figure failed to reproduce.
- **R113** State a zero-observed result as a **bar plus its power bound** ("zero of 15 ⇒ ~18%
  upper bound"), never as "never".
- **R131** The **guard's failure list IS the work-list** and stays red until done — a
  shrink-only allowlist ratchet.
- **R098** A detector is a **worklist, not a verdict**, and its input is the corpus of **escaped
  defects**, not imagination. When a human catches something mechanizable that a detector
  missed, extend the detector rather than noting it. *(Demoted from the body: its actionable
  half is `~/.claude/CLAUDE.md`'s "build the gate" applied to detectors.)*
- **R128** (B) A detector's **standing counts are context against a baseline, not per-run
  alarms**. The actionable signals are a self-test failure and a stale-snapshot warning.
- **R127** (B) Trace **comment-vs-string before counting occurrences** — prose *describing* a
  convention is not an instance of it. Join soft-wrapped prose into semantic units so a
  two-line contradiction is catchable.

## Assertion shapes `[body]`

- **R289** An oracle can pass or fail for a reason **adjacent to the one it claims to test**.
  R117, R119 and R122 are three instances (emptiness, type-not-value, lockstep derivation); the
  general form is the discriminator — name the neighbour the check rules out, and state what it
  would have to observe in order to fail. Two shapes in one session: a positive control chosen at
  the wrong **depth** was used to license an absence claim about nesting, so it could only ever
  prove the instrument worked at the depth already searched; and a fixture reddened a **different
  channel of the same tool** than the assertion named, which is indistinguishable from the named
  channel working. Both read as evidence at the time, and one of them was one step from a public
  accusation that an author had invented a citation.
- **R118** Assert on the **parsed structure**, never a substring of the stringified error, and
  never on another layer's framework-internal error text — the echoed request body satisfies
  the substring.
- **R119** `raises(SpecificError)` with **no value assertion** still passes when production
  swaps to a parent class. Assert the externally-visible value, not the type.
- **R117** A negative/counter assertion whose only check is **set-emptiness passes vacuously**
  on an empty response. Pair it with a non-empty anchor.
- **R120** The change's stated purpose has a **pin test**: a single-line revert of the
  production line must redden ≥1 test.
- **R122** Pin externally-visible constants (callback URLs, routes, wire values)
  **byte-immutable** with a test — and note that an oracle pinning an emitted value to the
  constant it is *derived from* moves in lockstep and can never fail.
- **R123** A grounded constant with **no test comparing it to its pinned source** lets a future
  drift reach the user with nothing red.
- **R121** (B) An **eagerly-derived table built at import** misses lazily-loaded members. Assert
  completeness at test time.
- **R126** (B) **Log-capture assertions** pass in isolation and fail in a full suite because
  other tests leave global logging state behind. Assert on behavior, not captured logs.

## Harness and fixtures `[body]`

- **R130** A harness supplying **"sane defaults" defeats any test probing the absence of that
  field**. Grep the harness for default-backfill of X before adding a validator for X.
- **R096** Fixtures that mirror the parser's own assumptions are a **self-referential oracle**.
  Commit ≥1 fixture from the real corpus, add a completeness oracle asserting a structural
  invariant over real data, and make a tolerant parser's silent skip **observable**.
  *(Demoted from the body: same family as the body's circularity rule.)*
- **R129** A **dispatcher routing by key must raise loudly on an unhandled key**, and when two
  sources can answer a question, rank them by authority and fail loudly on a miss — a silent
  default is how drift stays invisible.
- **R135** (B) A test client that **bypasses real auth middleware needs an explicit dependency
  override** — the bypass is silent.
- **R136** (B) **Generated files carry a DO-NOT-EDIT header** naming the regeneration command
  and the source revision; a hand edit without a source bump is a violation.
- **R137** (B) A **rate-limited harness call returns error text** — graders must classify it as
  FLAKE, not FAIL.

## Choosing the enforcement channel `[body]`

- **R107** Pick the enforcement channel by **what the invariant depends on**: statically
  checkable from local files → in-repo AST/config test · external or supply-chain state, or
  needs a real subprocess → off-the-shelf CI tool · admin scope or runtime measurement → verify
  script.
- **R114** Enable irreversibility only **after** the protective test is green N consecutive
  times — having the test is not having the gate. The order matters.
- **R101** A linter's **ignore list can disable the exact check you are relying on**. Read it
  before saying "the linter would have caught it". Asymmetry: the autofixer still prunes
  *unused* imports; the blind spot is *missing* ones.
- **R140** (C) Every threshold is a number, with **unvalidated defaults explicitly marked
  unvalidated**.

## Existing tests `[body]`

- **R132** Never **edit a test to pass**. Facing delete-vs-resurrect on a dead or broken test,
  default to resurrect with strengthened assertions — reducing test surface is a regression.
- **R133** (B) A test **pinning a dead shape gets deleted, not maintained**.
  **Discriminator against R132: does the pinned shape still exist in production?** Both rules
  are real; this question decides which fires.
- **R139** (B) Every fixed bug becomes a **blocking hook or guard test** (executable postmortem).
  Largely covered by `~/.claude/CLAUDE.md`'s "build the gate".
