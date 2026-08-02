The report file was blocked by a harness policy on subagent file writes, so the full report follows here in text. (Flagging explicitly since you asked for the file at that path — the content is complete, only the delivery channel changed.)

# salesagent skills audit — collision surface for four new user-level skills

Scope: the 8 skills at `/Users/quantum/Documents/ComputedChaos/salesagent/.claude/skills/`, read in full (SKILL.md + `agent-db/agent-db.sh`), against the 80 arbitration rules in `result-arbitration.json`. Read-only; nothing in the repo was modified.

## Bottom line

- **Two hard collisions**, both semantic (the two skills give contradictory instructions), not merely overlapping: `prebid-adcp` × `verify-spec`, and `testing-ci` × `guard`. Both are fixable entirely inside the new skills' descriptions and bodies. No change to an existing skill is required.
- **One trigger collision**: `review-practice` × `audit`. `audit`'s description opens with the words "code review audit", which is the exact magnet a PR-review skill needs. Fixable by naming.
- `git-workflow` collides with **nothing** in salesagent. It is the safe one.
- **Frontmatter: all 8 load.** Every block parses as valid YAML, every `name` is a valid slug matching its directory, every `description` is a string well under the limit. The non-spec `args:` key in 7 of them is inert. Nothing here blocks loading.
- **Load-bearing correction to the brief**: 5 of the 8 skills have a Step 1 that cannot execute on this machine. `.claude/scripts/cook_formula.py` does not exist anywhere in the repo, `bd` is not installed, and 3 of the 5 referenced formulas are absent. This changes the collision calculus — a mis-routed prompt does not land on a working alternative, it lands on a missing file. Details in §4.

---

## 1. Collisions

Ranked by expected damage = (trigger overlap) × (how wrong the wrong pick is) × (how often it fires in salesagent).

### 1.1 CRITICAL — `prebid-adcp` × `verify-spec`

**Overlapping scope:** what counts as authoritative for AdCP protocol behavior.

`verify-spec`'s description: *"Verify every test expectation in entity test suites against the authoritative adcp spec and library sources… Flags discrepancies where our tests assume behavior the spec doesn't define."* Trigger surface: `adcp spec`, `authoritative`, `verify`, `spec`, `library sources`, `discrepancies`.

`prebid-adcp` (rules 30/102, 101, 107, 65) will carry: `AdCP`, `spec prose`, `conformance storyboard`, `pinned version`, `cite section+version`, `SDK`, `error taxonomy`. The overlap on "AdCP spec" is near-total, and in salesagent nearly every task touches AdCP — so both are live candidates constantly.

**Why the wrong pick changes the answer, not just the route.** The two disagree on the authority order:

| | `verify-spec` (existing) | `prebid-adcp` rule 30/102 (new) |
|---|---|---|
| Authority #1 | JSON schemas at `dist/schemas/3.0.0-beta.3/core/` + OpenAPI | Spec **prose** + the graded conformance storyboard for the **derived** pin, fetched verbatim via `gh api` |
| Authority #2 | `adcp-client-python` Pydantic models — described as *"The Python implementation"* | SDK types/error codes/reference impls are *"a read-only cross-check, **never** the authority"* |
| Version | Hardcodes `3.0.0-beta.3` in the entity→spec table | Rule 101: read `ADCP_VERSION` / `adcp.get_adcp_spec_version()` per-wheel; *"any literal version quoted in a rule is already stale"* |
| Sources | Local clones at `/Users/konst/projects/adcp` and `/adcp-client-python` | `gh api` against the spec repo |

`/Users/konst` **does not exist on this machine** (checked). So `verify-spec`'s two primary source paths are dead, and its third (`adcp-req`) is dead too.

This conflict has already bitten once and is already documented in the repo. `/Users/quantum/Documents/ComputedChaos/salesagent/.claude/agents/review-spec-conformance.md:39` reads:

> You drive the project's `verify-spec` skill — but its stored copy hardcodes a stale local clone path and an old spec pin. IGNORE those; re-derive the live version (below). Strip the beads/formula layer.

and the same file's opening cites PR #1312, which *"built the INVERSE of the idempotency spec and survived 3 review rounds because it was grounded in an SDK error code, not the spec prose"* — which is verbatim the failure mode `prebid-adcp` rule 30 exists to prevent, and verbatim what `verify-spec`'s authority table would lead an agent to do.

The existing workaround only protects the path that goes through `review-spec-conformance`. A user-level `prebid-adcp` fires everywhere, including the paths that don't.

**Fix (in the new skill, not the old one).** Two lines in `prebid-adcp`:
1. Description states the authority order as its subject, not as a side effect — e.g. *"…grounds AdCP behavior in spec prose and the conformance storyboard for the pin derived at runtime; SDK types and error codes are a cross-check, never the authority."* This makes it win "is this spec-correct?" prompts on merit rather than by luck.
2. Body carries one explicit precedence line: **when a project skill or doc states a different source of truth for AdCP, this rule wins on the authority question; the project skill still owns its own workflow.** That resolves the contradiction without touching `verify-spec`.

### 1.2 CRITICAL — `testing-ci` × `guard`

**Overlapping scope:** whether to author a repo structural guard at all.

`guard`'s description: *"Create structural guard tests that enforce architecture principles on every `make quality` run. Guards are AST-scanning tests that prevent categories of violations automatically. Available guards: schema-inheritance, boundary-completeness, query-type-safety, no-error-dicts."* Its body: each guard gets a file at `tests/unit/test_architecture_{guard_name}.py`.

`testing-ci` rule 56, as currently distilled:

> Personal harness artifacts stay gitignored — run `git check-ignore <path>` before creating any file under tests/ or src/. **Enforce conventions in a private detector, never a repo guard.** *(detail)* A `tests/unit/test_architecture_*.py` guard runs on every contributor's `make quality` and CI; gating other people's builds is a shared-repo decision, out of bounds for personal tooling.

That names `tests/unit/test_architecture_*.py` — the exact artifact `guard` exists to produce — and forbids it in an unqualified sentence. The rule's *intended* scope is Chris's private review tooling; the sentence as written reads absolute. An agent in salesagent asked "add a guard for X" that loads `testing-ci` can talk itself out of doing the thing `guard` is for.

`testing-ci` rules 31, 78, 75 and 54 add further overlap on the same vocabulary (`guard`, `allowlist`, `matcher`, `make quality`) — but those are complementary (they say how to check a guard is real, not whether to build one), so they are not the problem. Rule 56 is.

The repo does sanction repo guards: `/Users/quantum/Documents/ComputedChaos/salesagent/.claude/agents/review-architecture-guards.md:37` — *"You may drive the project's `guard` skill for creating new guards, but strip its beads/`cook_formula.py` layer"* — and the repo runs ~50 of them on `make quality`.

**Fix.** Qualify rule 56 in the new skill to the case it was learned from: *"**Your own** review/harness tooling stays gitignored… enforce **your personal** conventions in a private detector, never by adding a guard to a shared repo's `make quality`. A project's own sanctioned guard-authoring workflow is out of scope for this rule."* One clause; preserves the rule; removes the contradiction.

**Ranking note.** 1.2 is an equally hard contradiction but I ranked it second on frequency: `guard`'s workflow is already non-executable end-to-end (§4), whereas `verify-spec` is actively driven on every PR touching schemas or tool `_impl`s. Re-rank if you weight severity over frequency.

### 1.3 HIGH — `review-practice` × `audit`

**Overlapping scope:** the words "code review" and "audit", and the concept "findings".

`audit`'s description: *"**Run a repeatable code review audit** on migration changes. Inventories files by architectural layer, **reviews** each layer against #1050/#1066 principles, and **files beads issues for findings**."*

The first five words are the highest-signal part of a description, and they are the exact phrase a PR-review skill needs to own. Its actual scope is far narrower than those words imply: a specific, now-historical migration keyed to issues #1050/#1066.

The wrong pick is expensive, because `audit`'s Step 1 runs `.claude/scripts/cook_formula.py` (**absent**) with `.claude/formulas/migration-audit.yaml` (**absent**), and its Step 2 is `bd ready → bd show → bd close` with `bd` **not installed** — while CORE rule 109 records that Chris has *"no beads/`bd` workflow"*. So a generic "review these changes" that routes to `audit` produces a missing-file error and a workflow Chris doesn't run.

Adding `review-practice` improves routing on net (there is finally a correct target), but it also creates a two-candidate race. The discriminator has to be explicit.

**Fix.** Name and describe `review-practice` around the artifact and the verbs `audit` does not use — *PR*, *review threads*, *findings ledger*, *dispositions*, *re-review*, *severity* — and keep the bare words "audit" and "code review audit" out of its description. See §2.

*(Optional, flagged because you said the bar is high: one-line narrowing of `audit`'s description to `Migration-era layer-by-layer audit (#1050/#1066) driven by the beads formula pipeline` would end this collision at the source. It is the single highest-value edit available among the 8 — but it edits a skill you said to leave alone, and the naming fix above achieves most of the benefit. Your call.)*

### 1.4 MEDIUM — `testing-ci` × `derive-tests` / `surface` / `integrate`

Trigger-only; no contradiction. All three existing skills are test-**authoring** pipelines (obligations → tests, entities → surface maps, xfails → integration tests). `testing-ci` is test-**strength verification** (mutation testing, selector honesty, guard completeness, CI trust).

The risk is entirely in phrasing. If `testing-ci`'s description contains *write tests*, *add tests*, *test coverage*, or *generate tests*, it will poach all three — and two of the three (`surface`, `integrate`) are also `cook_formula`-dependent and non-executable, so a mis-route is a dead end in both directions.

**Fix.** Describe `testing-ci` in verification verbs only: *prove*, *mutate*, *falsify*, *verify a test actually fails*, *trust a CI verdict*. Never *write* or *add*.

One phrasing hazard worth naming: rule 5 says *"never delete a test to close a gap."* `surface` deliberately generates `@pytest.mark.skip` stubs and `integrate` has a `reconcile-xfail` atom that removes xfail markers. Those are compatible with rule 5, but only if the rule says **"delete a test"** and not "remove a test marker" or "remove a skip." Keep the wording as-is.

### 1.5 LOW — `testing-ci` × `agent-db`

`agent-db` is the healthiest of the 8 — a working script, fixed as recently as 2026-06-16, and referenced directly from `CLAUDE.md:537`. `testing-ci` rules 26/77/91/108 are about *running* suites, which is adjacent to *"Use this before running integration tests in a worktree agent."*

**Fix.** Keep provisioning language (*database*, *container*, *Postgres*, *start the stack*) out of `testing-ci`'s description entirely. It doesn't need it, and `agent-db` should win those unambiguously.

Related gap, not a collision: the repo's `review-charter.md` §2 documents three agent-db-specific false-greens (stale `eval` port desync, concurrent-container contention producing spurious setup ERRORs, persistent schema masking fresh-DB `UndefinedTable`) that the `testing-ci` bucket does not carry. If `testing-ci` claims the CI-trust space globally, it will be consulted in salesagent while knowing three fewer false-green modes than the repo does. Not a blocker; worth a "defer to a project charter's masking-gotcha list where one exists" line.

### 1.6 NONE — `git-workflow` × anything

No skill, agent, or command in salesagent owns git/gh mechanics as a trigger. `agent-db` is Docker, not git. `git-workflow` is the one you can ship without collision analysis.

### 1.7 Between your own four new skills

You are authoring all four, so these are cheap to fix now and expensive later:

- **Rule 91** (testing-ci: assert `git rev-parse HEAD` + clean `git status --porcelain` before trusting a branch run) and **rules 1/10** (git-workflow: confirm a commit landed with `git rev-parse HEAD` + `git status`) are the same mechanism at two scopes. Keep 91 in `testing-ci` (it gates test runs), 1/10 in `git-workflow`. Do not put either in both.
- **Rule 97** (git-workflow: `mergeStateStatus=DIRTY` makes GitHub skip `pull_request` workflows; assert runs exist for the pushed SHA) is CI-shaped and could equally live in `testing-ci`. Either home is defensible — pick one.
- **Rules 66 and 92** (review-practice: two-dot vs three-dot diff; `git log -G` for provenance) are git mechanics living in `review-practice`. That is the right home — they are review procedures — but it means `git-workflow`'s description must not claim *diffing branches* or *comparing against main*, or it will poach them.
- **Rule 59** (prebid-adcp: *"treat press and vendor blogs as leads only — ground external-system claims in the installed artifact, then the spec repo, then source"*) is generic research hygiene with no AdCP content. Filed under `prebid-adcp` it only fires when AdCP is already in scope, which is where it is least needed. Consider CORE or `review-practice`.

---

## 2. Naming

| Proposed | Verdict | Reason |
|---|---|---|
| `git-workflow` | **Keep** | No collision. Minor: "workflow" is overloaded in salesagent (`.claude/rules/workflows/` holds beads-, tdd-, research-workflow) but those are rules files, not skills, so there is no selection contest. `git-mechanics` reads more precisely — the content is verification mechanics, not a pipeline — but this is preference, not a defect. |
| `review-practice` | **Rename → `pr-review-method`** | Three reasons. (a) It collides head-on with `audit`'s "code review audit" opener (§1.3). (b) It sits in a crowded prefix: salesagent has 8 agents named `review-*`, a `/full-review` command, the built-in `/code-review`, and your own user-level **`review-prompt`** skill — a "review this" prompt already has many candidates, and `review-practice`/`review-prompt` are one token apart at the same scope level. (c) "practice" is vague; "method" plus the `pr-` prefix states the artifact and that it is methodology. Alternate: `review-discipline` (matches the charter's own word, "shared operating discipline") if you prefer continuity with the repo's vocabulary. |
| `testing-ci` | **Keep the name; rewrite the description** | The name collides with nothing. Note that `test-integrity` is **not** available as an alternative — `.claude/agents/review-test-integrity.md` already owns that phrase in this repo. The `testing-ci` problems are all description-level (§1.2, §1.4, §1.5), and the name bundling two subjects (test strength + CI trust) is honest about its contents. |
| `prebid-adcp` | **Keep** | No existing skill has `prebid` or `adcp` in its name, so name-level routing is unambiguous — which is exactly why the §1.1 collision is dangerous: it is invisible at the name layer and lives entirely in the description. Fix the description, keep the name. |

---

## 3. Trigger quality of the existing 8

Criterion: does the description name a **condition** ("use when X happens to Y") in vocabulary a real prompt would contain, or does it only describe internals?

**Strong**

- **`agent-db`** — the best of the eight. *"Use this before running integration tests in a worktree agent."* Concrete condition, concrete nouns (PostgreSQL, container, worktree, port), and reinforced independently by `CLAUDE.md:537`. Nothing to fix.
- **`derive-tests`** — names the artifact, the hard gate, and the alternative it replaces. Weakness: it fires only on house vocabulary ("obligation", "derive tests", "harness"). *"Add a test for UC-004-MAIN-01"* — the natural phrasing — contains none of those and will miss.

**Medium**

- **`inspect-bdd-steps`** — the condition sentence is right (*"Use after writing or modifying BDD step definitions to catch assertion mismatches"*) but it is **last**, after three lines spent on internals (*"Pass 1 (Sonnet)… Pass 2 (Opus)…"*). That burns the highest-signal region of the description on implementation detail, and it pins two model names — which CORE rule 80 says ages badly, and which are already stale against the current lineup. Moving the condition sentence first would materially improve firing. Lowest-risk improvement available among the 8, if you ever revisit them.
- **`guard`** — good keyword surface (the four guard names are searchable terms) but **no "use when" clause at all**. It fires on *"create a guard"* and misses *"stop this class of violation from recurring"* / *"enforce this invariant automatically"* — which is how the need is actually phrased.

**Weak**

- **`surface`** — the only trigger anchor is house vocabulary ("test surface", "test-obligations", "entity"), and its one condition sentence is *"Run this before /remediate"* — gating on a command that **does not exist** (`.claude/commands/` contains only `full-review`, `obligation-team`, `research`, `team`). No phrasing a user would actually type.
- **`verify-spec`** — decent keywords ("adcp spec", "spec permalinks", "discrepancies") but its condition is *"Run this after /surface and before /remediate"*, gating on one nonexistent command, and its body content is stale in three ways (§1.1). Weak trigger **and** misleading payload.
- **`integrate`** — weakest. After a usable first line (*"Derive integration tests from existing unit test xfails and UNSPECIFIED stubs"*), the rest is an internal formula dump: *"Uses integration-from-stub formula: catalog → review → triage → architect → write-integration → fix-green → reconcile-xfail → verify → commit… cross-references against CRIT-1..CRIT-11 findings."* Tokens like `integration-from-stub` and `CRIT-1..CRIT-11` appear in no user prompt; they dilute the embedding around the one line that would have matched.
- **`audit`** — the worst combination: **over-broad and under-scoped simultaneously.** It wins generic "review"/"audit" prompts on its opening words while its real scope is one historical migration, and its first executable step is a missing file. This is the description most in need of narrowing and the one that most directly threatens your `review-practice`.

---

## 4. Redundancy, and the health finding that reframes it

### 4.1 Five of the eight cannot execute their own Step 1

Observed, this checkout, today:

| Referenced by | Path | State |
|---|---|---|
| audit, guard, integrate, surface, verify-spec | `.claude/scripts/cook_formula.py` | **absent** (repo-wide `find` returns nothing) |
| audit | `.claude/formulas/migration-audit.yaml` | **absent** |
| guard | `.claude/formulas/structural-guard.yaml` | **absent** |
| integrate | `.claude/formulas/integration-from-stub.yaml` | **absent** |
| surface | `.claude/formulas/entity-test-surface.yaml` | present |
| verify-spec | `.claude/formulas/verify-spec.yaml` | present |
| audit, guard, integrate, surface, verify-spec (Step 2) | `bd` (beads) | **not installed** |
| audit, guard, integrate, surface, derive-tests ("See Also") | `/remediate`, `/mol-execute`, `/obligation-test` | **absent** |
| derive-tests (Step 1, See Also) | `.agent-index/harness/*.pyi`, `.agent-index/factories.pyi` | **absent** |
| verify-spec | `/Users/konst/projects/adcp`, `/adcp-client-python`, `/adcp-req` | **absent** |

The surviving cook-free content is real and is what actually gets used: `derive-tests`' harness protocol (all 6 harness envs and the gold-standard meta-test exist), `inspect-bdd-steps`' script (`.claude/scripts/inspect_bdd_steps.py`, 18 KB, present), and `agent-db` (working).

This is corroborated in two places rather than being my inference: `review-architecture-guards.md:37` says drive `guard` *"but strip its beads/`cook_formula.py` layer"*, and `review-spec-conformance.md:39` says drive `verify-spec` but *"strip the beads/formula layer"* and ignore its stale paths. The live harness already routes around the dead half.

**Why this matters for your four, not as a request to fix anything:** the collision cost is higher than "the wrong skill gets picked." For `audit`, `guard`, `integrate`, `surface` and `verify-spec`, the wrong pick means the agent executes a command that isn't there. That is the argument for spending the effort on precise descriptions in the new skills rather than assuming a mis-route degrades gracefully.

### 4.2 The real content twin is `review-charter.md`, not any skill

`/Users/quantum/Documents/ComputedChaos/salesagent/.claude/rules/private/review-charter.md` (150 lines, gitignored, the mandatory Step-0 read for all 8 `review-*` agents and `/full-review`) already encodes most of the `review-practice` bucket, plus parts of `testing-ci` and CORE:

| Charter § | Arbitration rule |
|---|---|
| §1.1 / §1.1b re-derive numbers, prior rounds are claims | review-practice 61/7 |
| §1.3 empirical over static, assert HEAD before trusting a run | testing-ci 91 |
| §1.4 symmetric verification, empty result is a hypothesis | review-practice 11, 15 |
| §1.5b count the copies before proposing the fix | review-practice 13/55 |
| §1.5c adoption completeness, N adopted / M eligible | review-practice 38/82 |
| §1.5d short-circuit coverage illusion, one test per operand | testing-ci 75 |
| §1.6 provenance before "pre-existing" (`git log -G` + site-set diff + blame) | review-practice 92 |
| §1.7 / §1.7b / §1.7c propose-never-apply; inherited items; infra-can't-host | review-practice 71, 94, 32 |
| §1.8 banned language, no "optional"/"non-blocking" disposition | CORE 85/52; review-practice 48, 58, 43/50 |
| §1.9 output hygiene, fenced not blockquoted, strip internal vocabulary | CORE 45; review-practice 42 |
| §1.10 don't alarm mid-operation | git-workflow 40 |
| §1.11 semantic SSOT is invisible to structural guards | review-practice 73/76 |
| §1.12 claimed invariant ⇒ failing oracle, mutation-test defensive clauses | testing-ci 9 |
| §1.13 name patterns, not people | CORE 19/27/51 |
| §2 masking-gotcha doctrine (10 documented false-greens) | testing-ci 108; git-workflow 97; CORE 22/3/2 |

This is not a skill-selection collision — the charter is a rules file loaded by explicit Step-0 path, so nothing competes for selection. It is a **divergence risk**: two copies of one doctrine, one repo-local and one global, and the repo-local one is *richer* (each rule carries the specific miss that produced it, with PR numbers and measured counter-examples). If the terser global copy is what an agent reads in salesagent and the two drift, salesagent reviews get worse.

**Cheapest mitigation, and it lives in your new skill:** one line in `review-practice`/`pr-review-method` — *"If the project defines its own reviewer charter or review rules, that is authoritative and more specific; this skill is the default where none exists, and never overrides a project charter."* Same pattern works for `testing-ci` w.r.t. the charter's masking-gotcha list.

### 4.3 Duplicate skill copies in nested worktrees

`.claude/worktrees/` holds three live git worktrees (`agent-a0ffd17a442293f41`, `agent-a9554564f02faef83`, `agent-af86ee1e896744798`), each containing a full copy of `.claude/skills/`. All three are at `e5f674e38` (2026-07-30) and `agent-db.sh` is byte-identical to canonical in all three, so nothing is shadowed **right now**. Flagging only because it is a standing divergence surface, and because the charter's own §2 gotcha 9 and `full-review.md` Step 4 both record that this exact directory previously broke a worktree-located detector. No action implied.

---

## 5. Frontmatter validity

All 8 parse. Machine-checked with `yaml.safe_load` on each `---` block:

| skill | keys | name valid slug / matches dir | description type, length | body lines |
|---|---|---|---|---|
| agent-db | name, description | yes / yes | str, 206 | 58 |
| audit | name, description, **args** | yes / yes | str, 239 | 93 |
| derive-tests | name, description, **args** | yes / yes | str, 266 | 502 |
| guard | name, description, **args** | yes / yes | str, 275 | 77 |
| inspect-bdd-steps | name, description, **args** | yes / yes | str, 399 | 50 |
| integrate | name, description, **args** | yes / yes | str, 371 | 143 |
| surface | name, description, **args** | yes / yes | str, 265 | 86 |
| verify-spec | name, description, **args** | yes / yes | str, 285 | 163 |

**Nothing blocks loading.** Three observations, none of them defects that fire today:

1. **`args:` is not a SKILL.md frontmatter field.** Claude Code's skill loader recognizes `name`, `description`, and optional fields like `allowed-tools`; unrecognized keys are ignored, so these are inert. The equivalent field for a *command* is `argument-hint`, which the repo uses correctly in `.claude/commands/full-review.md`. The 7 skills carrying `args` look like slash-command frontmatter that survived a conversion to skills.
2. **Type inconsistency inside `args`.** `audit` has `args: [audit-target]`, which YAML parses as a **list** `["audit-target"]`; the other six parse as **strings**. Inert while nothing reads the key; it would break the first validator that assumes a string.
3. **`derive-tests` is 502 body lines**, well past the ~500-line navigation-hub guideline and roughly 6× the median of the other seven. It is a single flat file with no `references/` split. Working as is; noted only because it is the one skill where a future edit is likely to be expensive.

---

## Verification note

**Ran / read:** all 8 `SKILL.md` in full; `agent-db/agent-db.sh` in full; `result-arbitration.json` (all 80 rules, `core_count`, `coverage_check`, `disagreement_notes`); `review-charter.md`; `commands/full-review.md`; frontmatter and descriptions of all 10 `.claude/agents/*.md`, with `review-test-integrity`, `review-architecture-guards`, `review-spec-conformance` read in depth. Existence checks on every script, formula, command, harness file, `.agent-index` path and local clone path cited by a skill. YAML parse of all 8 frontmatter blocks. `git log` per skill directory. `git worktree list` and a byte-diff of the three nested worktree skill copies.

**Did not check:** whether any of the 8 skills actually fired in the 159 sessions (I have no session transcripts — the "these run today" premise is yours, and my §4.1 findings are about executability, not usage); the contents of `reviewer-tooling.md` and the 5 `rules/patterns` + 7 `rules/workflows` files beyond line counts; the per-project memory directory at `/Users/quantum/.claude/projects/-Users-quantum-Documents-ComputedChaos-salesagent/memory/` that the review agents cite; the 4 remaining review agents' bodies; whether `cook_formula.py` exists in some other checkout or was removed deliberately (it is referenced at `/Users/konst/projects/pi-agentic-coding/...` in `agents/executor.md:116`, a path that does not exist here — so the tool it came from appears to be a machine that isn't this one).