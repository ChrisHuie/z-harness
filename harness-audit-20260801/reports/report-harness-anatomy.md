All 13 detectors are invoked — that closes a FACTS.md gap. Here is the complete map.

---

# Harness anatomy — salesagent review suite

Token figures use FACTS.md's 3.8 chars/token (±3-6k RMS). Byte counts are exact.

## Three corrections to FACTS.md first

**1. The per-lens Step-0 cost is 87% higher than recorded.** FACTS.md counts charter (39,867 B) + reviewer-tooling (13,627 B) = 53,494 B. It misses that `review-charter.md:136-147` **§5 mandates nine more memory files for every agent**:

```
## 5. Mandatory Step-0 reads (every agent, before catalog work)
Read these under <MEMORY_DIR>, then your agent-specific catalog list:
- feedback_truth_over_optimism.md ... (9 files)
```

Those nine total **46,516 B**. True shared Step-0 = **100,010 B ≈ 26,318 tok**, not 13.4k.

**2. CLAUDE.md is not injected into subagents.** Measured 0/301 lens-agent transcripts contain the CLAUDE.md injection banner. The 750-line CLAUDE.md and 443-line `tests/CLAUDE.md` are **main-thread-only** costs. Only `review-admin-ui` pays for CLAUDE.md, by explicitly reading it (`review-admin-ui.md:27-28`).

**3. Charter §5 is 41% complied with, and bimodally.** Across 301 identified lens runs:

| §5 files read (of 9) | runs |
|---|---|
| 0 | 128 (43%) |
| 1-8 | 85 |
| 9 | 88 (29%) |

charter read in 89% of runs, reviewer-tooling in 72%. The split is uniform across all 8 lenses (31-51% read zero) — this is not a per-lens defect but a property of the §5 list itself. **The harness pays for the discipline sometimes and can never rely on it.**

---

## 1. Inventory and the cost of one 8-lens round

Total harness footprint, excluding worktrees/notes/reports: **1,175,309 B ≈ 309k tokens**.

| Group | Files | Bytes | Load class |
|---|---|---|---|
| `memory/` | 169 | 525,937 | **on-demand**; 46 files (173,466 B) are mandated Step-0 |
| `rules/private/detectors/` | 13 `.py` | 155,817 | **never loaded** — executed as subprocesses |
| `scripts/` | 6 | 93,759 | **never loaded** — `inspect_bdd_steps.py` executed |
| `agents/` | 10 | 88,775 | **per-agent** (definition = system prompt); descriptions always-on |
| `rules/private/*.md` | 3 | 75,028 | **per-agent** Step-0 (charter, tooling, harness-upgrade-spec) |
| `formulas/` | 4 `.yaml` | 60,227 | **never** — see §3 |
| `CLAUDE.md` + `tests/CLAUDE.md` | 2 | 53,296 | **always-on, main thread only** |
| `skills/` | 9 | 51,241 | on-demand; descriptions always-on |
| `commands/` | 4 | 46,404 | on-demand (`/full-review` = 16,796 B) |
| `rules/patterns/` + `workflows/` | 10 | 24,825 | on-demand |

**Always-on floor contributed by the harness:** the 10 agent descriptions (3,201 B) + 8 skill descriptions (2,387 B) = **5,588 B ≈ 1,471 tok on every one of the 41,859 API calls**.

### The round cost

| Lens | agent def | own catalog | shared Step-0 | total B | ~tok |
|---|---|---|---|---|---|
| admin-ui | 4,594 | 0 | 100,010 | 104,604 | 27,527 |
| architecture-guards | 7,648 | 19,362 | 100,010 | 127,020 | 33,426 |
| bdd | 8,250 | 19,030 | 100,010 | 127,290 | 33,497 |
| code-patterns | 14,453 | 36,468 | 100,010 | 150,931 | 39,719 |
| error-wire | 13,084 | 40,367 | 100,010 | 153,461 | 40,384 |
| security | 7,770 | 18,855 | 100,010 | 126,635 | 33,325 |
| spec-conformance | 11,563 | 15,458 | 100,010 | 127,031 | 33,429 |
| test-integrity | 11,284 | 15,692 | 100,010 | 126,986 | 33,417 |
| **ROUND** | | | | **1,043,958** | **274,726** |

**One full 8-lens round costs ~275k tokens of instruction text before a single line of diff is read.** That is the number nobody had computed.

- Shared portion paid 8x: **800,080 B ≈ 210,547 tok**
- Same content paid once: 100,010 B ≈ 26,318 tok
- **Pure redundancy: 700,070 B ≈ 184,229 tok per round** — 67% of the round.

At measured compliance rates the empirical figure is **~516,571 B ≈ 136k tok/round** shared. Against FACTS.md's 738 dispatches (~92 rounds), the shared-text total is **~12.5M tokens** at empirical rates, ~19M at full compliance — above FACTS.md's ~10M estimate.

---

## 2. Duplication matrix — the highest-value finding

### Tier 1: the flagship — one lesson in three files, each paid separately

The "auth seam adopted in 1 of 5 sites" miss appears **verbatim, 190-260 bytes, in three locations**:

| Location | Path |
|---|---|
| Charter §1.5c | `.claude/rules/private/review-charter.md:24` |
| Agent def | `.claude/agents/review-code-patterns.md:61` |
| Memory file | `memory/feedback_new_abstraction_needs_adoption_completeness.md` |

Shared text: *"a PR extracted the right auth seam and wired it into **1 of 5** eligible sites; the four holdouts kept routing their untyped branch through a helper that interpolates `str(exc)` onto the buyer wire — the exact disclosure the new seam existed to prevent."*

A `review-code-patterns` run reads this **twice** (charter + own definition) every single dispatch.

### Tier 2: the charter has absorbed its own memory corpus

Six memory files are restated in the charter at 6-12% verbatim and far higher semantically:

| Memory file | words | verbatim-in-charter | charter § |
|---|---|---|---|
| `feedback_new_abstraction_needs_adoption_completeness` | 477 | 363 B (12%) | §1.5c |
| `feedback_short_circuit_coverage_illusion` | 323 | 178 B (9%) | §1.5d |
| `feedback_defect_recurrence_is_the_root_cause` | 337 | 172 B (8%) | §1.5b |
| `feedback_infra_limitation_needs_cost_estimate` | 290 | 132 B (8%) | §1.7c |
| `feedback_subagent_mechanism_is_a_claim` | 280 | 128 B (7%) | §1.7d |
| `reference_reload_captures_active_mock` | 344 | 137 B (6%) | §2.10 |

**`feedback_verify_reviewer_fixes_against_code` (981 words, 6,383 B) is the worst case**: it is restated in charter §1.7b *and* is item 8 of the §5 mandatory list — an obedient agent pays for the same lesson twice in one dispatch.

### Tier 3: charter §2 ↔ reviewer-tooling — same content, fully reworded

Charter §2 enumerates 10 false-greens; reviewer-tooling §A-§E gives detection recipes for the same 10. Overlap is only **21 shingles** — near-total rewording. Both are mandatory. Examples of the same fact in two voices:

- tox banner: charter §2.1 *"tox prints its own 'congratulations :)' banner when ITS envs exit 0"* / tooling §A *"tox prints its own `congratulations :)` banner whenever ITS envs exit 0"*
- `make quality`: charter §2 closing paragraph / tooling §A bullet 3
- the unit+integration mock escape: charter §2.10 (a 1,400-byte paragraph) / tooling §C final bullet (a 700-byte restatement)

Because they are worded differently, no agent can safely skip either. **13,627 B of reviewer-tooling is largely a second telling of 39,867 B of charter.**

### Tier 4: `/full-review` restates the charter

48 shingles overlap, including a 174-byte verbatim run of the SSOT-synthesis rationale (charter §4b.0 ↔ `full-review.md:53`). The command also re-derives charter §3's report envelope, §4b.5's disposition ladder, and §4c's readiness gate.

### Tier 5: dispatch conditions duplicated

`review-spec-conformance.md:49` and `full-review.md:47` both carry the full #1677 dormant-grader rationale (~700 B each) — orchestrator and agent each paying for the same paragraph.

---

## 3. Dead weight

### Referenced but missing

| Reference | Referenced from | Status |
|---|---|---|
| `.claude/scripts/cook_formula.py` | `audit`, `guard`, `integrate`, `surface`, `verify-spec` SKILL.md | **absent** |
| `/Users/konst/projects/pi-agentic-coding/.../cook_formula.py` | `agents/executor.md:116` | **absent** (`/Users/konst` does not exist) |
| `bd` (beads CLI) | same 5 skills + charter §3 + `full-review.md:85` | **not installed** (`which bd` → exit 1) |
| `/Users/konst/projects/adcp`, `adcp-client-python`, `adcp-req` | `verify-spec/SKILL.md` | **absent** |
| `.claude/agent-memory` → `/Users/konst/projects/salesagent/.claude/agent-memory` | symlink in `.claude/` | **broken symlink** |
| `.claude/research` → `/Users/konst/projects/salesagent/.claude/research` | symlink in `.claude/` | **broken symlink** |

Both broken symlinks are in `.gitignore` per charter:96, so they are invisible to git and to any reader who doesn't `ls -la`.

### Exists but never referenced or used

| Item | Bytes | Evidence |
|---|---|---|
| `agents/executor.md` | 7,731 | **0 dispatches** across all transcripts |
| `agents/qc-validator.md` | 2,398 | **0 dispatches**; referenced only by `rules/workflows/subagent-implementation-guide.md:25` |
| `formulas/*.yaml` | 60,227 | consumed only by `cook_formula.py`, which is absent |
| `skills/guard/SKILL.md` | 2,745 | **0 reads** in transcripts |
| `skills/integrate/SKILL.md` | 6,874 | **0 reads** in transcripts |
| `.claude/worktrees/agent-*` | **1.2 GB** | 3 orphaned dirs; **not in `git worktree list`** |

The 1.2 GB of orphaned worktrees is not merely disk waste — reviewer-tooling §G2 documents that a full data volume killed **four of six specialists mid-run** with `ENOSPC`, and names Docker as the dominant consumer. These three abandoned trees (each with its own `.venv`, `.mypy_cache`, and `beads.db`) are a second contributor to the exact failure the harness has a preflight block for.

Contradicting a plausible assumption: **there are zero orphaned memory files.** All 168 are indexed in `MEMORY.md`. And **all 13 detectors are genuinely invoked** (`ssot_docstring_duplication` in 88 of 500 recent transcripts, `citation_freshness` in 82, down to `github_workflow_duplication` in 2). That closes the FACTS.md gap "whether the 12 detectors are actually INVOKED" — they are, and there are 13, not 12.

Worth noting though: detectors are **mentioned** 10-20x more often than run (`bump_check` 265 mentions : 13 invocations; `sdk_spec_drift` 299 : 25). The prose describing each detector is paid on every dispatch; the detector runs rarely.

---

## 4. The workaround tax

Three agent definitions instruct the model to work around broken skills:

| Location | Text | Bytes |
|---|---|---|
| `review-architecture-guards.md:37` | "You may drive the project's `guard` skill for creating new guards, but strip its beads/`cook_formula.py` layer." | 111 |
| `review-bdd.md:31` | "...Strip any beads/formula layer." | 170 |
| `review-spec-conformance.md:34` | "...but its stored copy hardcodes a stale local clone path and an old spec pin. IGNORE those; re-derive the live version (below). Strip the beads/formula layer." | 204 |

**The instruction bytes are negligible — 485 B ≈ 128 tok per round.** That is not where the cost is.

The real tax is what the workaround fails to prevent: **`verify-spec/SKILL.md` was read 111 times.** At 6,367 B that is **706,737 B ≈ 186k tokens spent reading a skill that cannot execute Step 1** — it hardcodes three nonexistent `/Users/konst/` paths and calls an absent script. Adding `audit` (12 reads) and `surface` (3 reads):

**Broken-skill read tax: 754,161 B ≈ 198,463 tokens.**

Fixing the root cause — deleting the dead pipeline layer from `verify-spec` and re-pointing its spec source at the live derivation that `review-spec-conformance.md:43` already specifies — would recover essentially all of that, plus let `review-spec-conformance.md:34` drop from 204 B to zero.

---

## 5. The 8 lens definitions

**The boilerplate hypothesis in the brief is false.** Exact-line redundancy across all 8 is **5.2% (4,107 B of 78,646 B)**, and no lens opens with 40 shared lines — the Step 0 blocks run 682-1,135 B (roughly 9-15 lines).

Every duplicated line, complete:

| Occurrences | Waste | Line |
|---|---|---|
| 8x | 665 B | the reviewer-tooling absolute path |
| 8x | 651 B | the review-charter absolute path |
| 8x | 567 B | `## Step 0 — MANDATORY: read these FIRST...` |
| 5x | 516 B | `- Working-tree mode: git diff (+ --cached). PR mode: ...` |
| 4x+3x | 555 B | the memory-dir path preamble (two spellings: "Your catalog" / "Catalog") |
| 3x | 174 B | `- Emit the charter §3 format with the MANDATORY "What I could not verify" section.` |
| rest | 979 B | section headings (`## Scope / inputs`, `## Detection protocol (by cluster)`, …) |

Structural split per file:

| Lens | total | frontmatter | Step 0 | scope | return | **lens-specific body** |
|---|---|---|---|---|---|---|
| admin-ui | 4,594 | 454 | 682 | 259 | 384 | **2,815 (61%)** |
| architecture-guards | 7,648 | 480 | 915 | — | 487 | **5,766 (75%)** |
| bdd | 8,250 | 405 | 770 | 1,172 | 383 | **5,520 (67%)** |
| code-patterns | 14,453 | 440 | 1,135 | 325 | 973 | **11,580 (80%)** |
| error-wire | 13,084 | 514 | 987 | 301 | 703 | **10,579 (81%)** |
| security | 7,770 | 532 | 708 | 406 | 433 | **5,691 (73%)** |
| spec-conformance | 11,563 | 505 | 851 | 284 | 588 | **9,335 (81%)** |
| test-integrity | 11,284 | 483 | 777 | 254 | 484 | **9,286 (82%)** |

**61-82% of each definition is genuinely lens-specific.** These are well-factored documents. Pairwise 9-gram overlaps of 38-65 shingles are almost entirely the Step-0 paths and section headings above.

The redundancy is not *inside* the definitions — it is in **what they point at**. Each lens's ~850 B Step-0 block summons 100,010 B of shared reading. **A 118:1 amplification.** Compressing the definitions would save ~4 KB per round; compressing what they summon would save ~700 KB.

The one real intra-definition duplication is Tier 1 above: `review-code-patterns.md:61-62` restates charter §1.5c at length, and `review-test-integrity.md:86` restates charter §1.5d.

---

## 6. Retire, repair, or rebuild — the 5 broken skills

| Skill | Bytes | Reads | Verdict | Reason |
|---|---|---|---|---|
| **`verify-spec`** | 6,367 | **111** | **REPAIR** | Highest-traffic skill in the harness and the only broken one with real demand. `review-spec-conformance` drives it on every spec dispatch and pays 204 B/run telling the model to ignore it. The repair is small: delete the beads/`cook_formula` pipeline, replace the three `/Users/konst/` paths with the runtime derivation already written at `review-spec-conformance.md:43`. Recovers ~186k tokens. |
| **`audit`** | 3,169 | 12 | **RETIRE** | Its stated purpose — "reviews each layer against #1050/#1066 principles, files beads issues" — is a migration-era workflow tied to two closed PRs. Both its execution paths (`cook_formula.py`, `bd`) are dead, and the 8-lens suite now covers layer review. Nothing references it. |
| **`surface`** | 3,132 | 3 | **RETIRE** | Entire pipeline is `cook_formula.py` + `bd` + `formulas/entity-test-surface.yaml`. Chris does not use beads, so the "one obligation → one test" ledger has no store. `derive-tests` (17,798 B, 7 reads, no broken deps) is the live successor. |
| **`integrate`** | 6,874 | **0** | **RETIRE** | Zero reads, ever. Nine-atom formula pipeline entirely dependent on the absent `cook_formula.py`, plus "7 architecture docs and CRIT-1..CRIT-11 findings" that I could not locate. |
| **`guard`** | 2,745 | **0** | **REBUILD (small)** | Zero reads, and its pipeline is dead — but unlike the others it has a **live consumer**: `review-architecture-guards.md:37` still points at it, and charter §1 / `feedback_escalate_recurring_lessons_to_guards` make "promote a recurring lesson to a guard" a standing recommendation the suite emits. The capability is wanted; the implementation is not. Rebuild as a short SKILL.md wrapping the guard-authoring rules already written at `review-architecture-guards.md:70-72` (P20, P32), with no formula layer. |

Retiring `audit` + `surface` + `integrate` removes 13,175 B of skills and their 493 B of always-on descriptions, and makes `formulas/entity-test-surface.yaml` + `verify-spec.yaml` (31,934 B) provably dead.

**On `bd`:** it is referenced in three *live* places beyond the dead skills — charter §3 (`FOLLOW-UP — MUST be filed (issue / bd create / spawn_task)`), charter §4b.5, and `full-review.md:85`. Those are disposition-tracking instructions the orchestrator acts on every round. Since `bd` is not installed, each is an instruction to use a tool that will fail. **Keep the FOLLOW-UP discipline; drop `bd` from the three enumerations** so the model reaches for `gh issue create` or a task without first trying a missing binary.

---

## What I could not measure

- **Whether the ~275k tok/round is cache-read or cache-write.** FACTS.md establishes a 28.7x re-read multiplier corpus-wide, but I did not attribute cache state to these specific Step-0 reads. At 60.5% billed share for cache reads the *billed* cost is well below the token count; the *context-window* cost is not.
- **Why 43% of lens runs read zero §5 files.** I measured the rate, not the mechanism. Candidates I did not test: dispatch prompts that override Step 0, context pressure, or the §5 list sitting at charter line 136 of 151 — after ~37k bytes of prose.
- **The 3 orphaned worktrees' provenance.** They are not registered git worktrees; I did not determine which crashed run left them (reviewer-tooling §H bullet 6 documents a crash class that orphans isolation trees).
- **`harness-upgrade-spec.md` (21,534 B)** — I inventoried it but did not read it or trace its readers.
- **`obligation-team.md` (16,219 B) and `research.md` (5,310 B)** — 8 and 90 transcript mentions respectively; I did not audit their internals.
- The two transcript greps for `cook_formula.py` invocation context timed out at 5 minutes; the 14 mentions are unclassified as to whether they were attempted executions or the workaround instructions being quoted.

## Files referenced

- `/Users/quantum/Documents/ComputedChaos/salesagent/.claude/rules/private/review-charter.md` (§5 at lines 136-147; §1.5c at line 24; §4b.0 at line 108; §2.10 at line 53; gitignore warning at line 96)
- `/Users/quantum/Documents/ComputedChaos/salesagent/.claude/rules/private/reviewer-tooling.md` (§G2 ENOSPC at line 58; §H at lines 62-71)
- `/Users/quantum/Documents/ComputedChaos/salesagent/.claude/agents/review-code-patterns.md:61`
- `/Users/quantum/Documents/ComputedChaos/salesagent/.claude/agents/review-spec-conformance.md:34,43,49`
- `/Users/quantum/Documents/ComputedChaos/salesagent/.claude/agents/review-architecture-guards.md:37,70-72`
- `/Users/quantum/Documents/ComputedChaos/salesagent/.claude/agents/review-bdd.md:31`
- `/Users/quantum/Documents/ComputedChaos/salesagent/.claude/agents/executor.md:116`
- `/Users/quantum/Documents/ComputedChaos/salesagent/.claude/commands/full-review.md:47,53,85`
- `/Users/quantum/Documents/ComputedChaos/salesagent/.claude/skills/verify-spec/SKILL.md`
- `/Users/quantum/.claude/projects/-Users-quantum-Documents-ComputedChaos-salesagent/memory/` (168 files + MEMORY.md)