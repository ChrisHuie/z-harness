# Skills & memory: the plan

Repo-agnostic. Derived from 6 agents in wave 11 (`reports/report-{router,skillaudit,planaudit,
trigger,structure,diet}.md`). **Nothing has been executed.** Backup taken:
`PRE-MIGRATION-BACKUP/` (257 files) — `~/.claude` is NOT a git repo *(true at planning
time; a clone of `ChrisHuie/z-harness` since 2026-08-02)*, so deletions were otherwise
unrecoverable.

---

## 0a. HARD GATE — every salesagent lens is SKILL-DEAD. Fix before moving anything.

**All 10 agent definitions in `salesagent/.claude/agents/` carry an explicit `tools:`
allowlist, and none includes `Skill`:**

```
executor                    Bash Read Write Edit Glob Grep Task ToolSearch
qc-validator                Bash Read Grep Glob
review-{admin-ui, architecture-guards, bdd, code-patterns,
        error-wire, security, test-integrity}     Bash Read Grep Glob
review-spec-conformance                           Bash Read Grep Glob WebFetch
```

**Measured, not inferred:** an agent type with an explicit `tools: Read, Edit` allowlist
reports `Skill` **absent from its roster** AND **no skills listing in its context at all**.
An allowlist that omits `Skill` strips both channels. (Measured on a built-in agent type
declaring `tools:` the same way; the roster-construction path is shared. The 10 salesagent
definitions were read directly — the allowlists above are verbatim.)

**Consequence: routing 121 memories into skill bodies makes them 100% unreachable for the
eight review lenses they were written for.** Subagents in general fire skills fine — 5/5 with
a directive, 1/3 without, matching main-thread. It is specifically the `tools:` allowlist
that kills it, and **72% of all API calls are subagent**.

**The fix is one token per file: add `Skill` to all 10 `tools:` lists.** Ten one-line edits in
a gated repo. Until that lands, §3's migration must not run — it would strand knowledge more
thoroughly than the status quo, where a lens can at least `Read` a memory file with the tools
it already has.

**Also blocked by this class:** `~/.claude/settings.json` carries
`permissions.ask: ["Agent","Task"]` (added during this audit). In non-interactive `claude -p`
that resolves to a **denial**, and it survives `--permission-mode bypassPermissions`. Any
headless or cron run that dispatches agents is dead in the water. Interactive use is
unaffected. Not yet decided whether to keep it — but it must be a decision, not a surprise.

---

## 0. THE BLOCKER — RESOLVED 2026-08-02. Full record: `EXP-skill-delivery.md`

**Measured fix: one always-on imperative paragraph takes embedded-work skill firing from
1/5 to 5/5, through the channel a `CLAUDE.md` edit actually uses.**

| framing | directive | fired |
|---|---|---:|
| isolated | none | 8/8 |
| **embedded (real work)** | **none** | **1/5** |
| embedded | appended system block | 5/5 |
| **embedded** | **`CLAUDE.md` (shipping channel)** | **5/5** |

Two corrections this forces on the rest of this document:

- **§5: ADD the imperative. Whether to keep the table is UNTESTED — do not claim otherwise.**
  The 4-row routing table was present in **every** arm, including both 1/5 arms (all cells ran
  against the real `~/.claude`; the isolated-config approach was abandoned when it would not
  authenticate). So the experiment shows the table is **insufficient**, never that it is
  **necessary** — no arm ran imperative-without-table. An earlier revision of this file claimed
  arm C "refutes cutting the table." It does not. It refutes *the table alone being enough*,
  which is a different claim. The supported edit is the 55-word imperative; the table's 406 B
  is unjustified either way until someone runs that arm.
- **§3's routing to skill bodies is now sound.** It was not sound before this experiment.

**Why the original diagnosis read as fatal — and why the eval harness missed it:** all 8
skills score 100% on isolated test prompts. Real work presents the skill's topic as a
*sub-step*, and that framing answers 20%. The eval measured a framing real work never
produces. I reproduced that exact error before catching it — see `EXP-skill-delivery.md` §2.

### Corpus census — RE-AUDITED 2026-08-02 by independent re-scan. Counts hold; DENOMINATOR DOES NOT.

Re-derived from all 2,537 transcripts / 1.29 GB / 343,438 records, including the 1,928
subagent transcripts (76% of files). **Every count below reproduced exactly** — 227 `Skill`
blocks across 13 names, 91.1% eval-harness (133/146; and 146/146 = 100% eval-or-workshop),
14 mutating-git sessions with 0 fires, last invocation 2026-07-16T00:10:38Z, eval 24/24 POS
and 0/16 false-fire. **The instrument was correct**: it keyed on `tool_use.name == "Skill"`,
not a name grep — mention-to-invocation ratios run 3.5x–24.7x, so a grep would have reported
git-workflow at **39 transcripts instead of 0**. That trap was avoided.

**But "2,474 transcripts / 7.1 weeks" is the wrong denominator for every skill in the table.**
A direct instrument nobody had used — the harness's own `skill_listing` attachment, 2,002
records recording what was visible per dispatch — gives true first visibility:

| skill | first visible | window | dispatches it was LISTED on |
|---|---|---:|---:|
| craft-prompt, review-prompt | 2026-07-14T09:04Z | 18.9 d | 861–1,184 |
| craft-skill, craft-context-file | 2026-07-14T18:41Z | 18.5 d | 861–1,184 |
| **git-workflow, prebid-adcp, testing-ci, pr-review-method** | **2026-08-01T22:30Z** | **7.7 h** | **69 (63 transcripts)** |

**753 `skill_listing` records from 06-12 through 07-13 contain none of the eight.** No
user-level skill existed for **31.4 of the corpus's 50.4 days — 62% of the window.** A 17x
exposure difference was being reported as a like-for-like row in an 8-cell table. (Also: the
craft-* four were visible from 07-14, not "≥07-15" — `.ph-installed` is a re-install stamp,
as `install.sh:39` does `rm -rf` before copying. And the "13.4 hours" figure is
unreconstructible; true window is 7.7 h.)

**The premise survives, split across two weak halves — and "close to uninformative" overstated
the weakness.** In their 7.7 h the operational four were not merely idle: **14 transcripts
executed a mutating git/gh verb (git-workflow: 0 fires), 15 executed pytest/tox/gh run
(testing-ci: 0 fires).** Against the 20% embedded rate each rejects at **p ≈ 0.04**. Meanwhile
the craft-* four have the long window but a nearly empty *action* surface: **1** pre-audit
transcript actually wrote a `CLAUDE.md`/`AGENTS.md`, **0** wrote a `SKILL.md`. Neither half
carries the premise alone; together they do. But the claim reads roughly **two orders of
magnitude stronger** than its evidence.

**§0's resolution does not depend on any of this** — it rests on the 1/5 → 5/5 A/B, which is
independent of the census. What must be rewritten is the paragraph below.

**Three defects found in the original trigger work:**
- **A timezone bug**: `trig/nearmiss.py:12` assumes UTC-7; true offset is UTC-6, proved by
  `.ph-installed` against its own birthtime. All 8 eligibility cutoffs are one hour late
  (79 vs 86 eligible). Conservative direction; flips nothing.
- **A question marked undeterminable is closed.**
  `~/.claude/backups/memory-and-harness-20260801-122750/CLAUDE.md` — snapshotted **4 hours
  before the four skills were created** — is 4,079 B with **zero** occurrences of the four
  skill names and **no routing table**. The table was demonstrably not in force during the
  miss window.
- **§0 dropped its own strongest evidence in consolidation.** `report-trigger.md` carried a
  craft-* near-miss table (186 `CLAUDE.md`-mentioning sessions, 53 `SKILL.md`, 18
  write-a-prompt, 0 fires) — the *only* long-window support for the premise. §0 compressed it
  to the parenthetical "also silent for 17 days." **The load-bearing table did not survive
  summarisation** — the same structure-loss this audit measured in compaction, committed by hand.

**Blind spot, newly found:** 36 slash-command invocations (`/review-prompt` ×20,
`/craft-prompt` ×10, 6 MCP-form) emit **no `Skill` tool_use** and are invisible to the census.
All 36 sit in eval/workshop contexts so no conclusion moves — but **94 and 44 are floors, not
totals.**

**Superseded original finding**, retained for the counts, which reproduced:

**User-level skills do not fire.** Measured across 2,474 transcripts / 7.1 weeks:

```
review-prompt        94        git-workflow        0   NEVER
craft-prompt         44        pr-review-method    0   NEVER
craft-context-file    5        prebid-adcp         0   NEVER
craft-skill           3        testing-ci          0   NEVER
```

- **91% of all invocations came from the skills' own eval harness.** No user-level skill has
  ever fired in a project that was not its own workshop.
- Last invocation of ANY user-level skill: **2026-07-16 — 17 days before the corpus ends.**
- Near-miss: **14 sessions ran a mutating git/gh verb, 0 fired. 5 ran `git grep` — named
  verbatim in the description — 0 fired.**
- Yet all 8 score **100% hit / 0% false-fire on isolated test prompts.**

**Diagnosis: the failure is not trigger wording. Real work never presents as an isolated
prompt.** *(Caveat: the 4 operational skills were installed 2026-08-01 16:30, so their zero
covers ~13h. The craft-* four have been installed since ≥07-15 and are also silent for 17
days.)*

**Consequence: "skill bodies are free until invoked" is worthless if never invoked.** Moving
121 memories into skill bodies would make them LESS reachable than today — a memory can at
least be Read deliberately. This is the same false-green shape as the 12 broken detectors,
one tier up.

**Resolve first.** Options, untested: (a) invoke skills explicitly by name as a habit;
(b) a hook that suggests a skill on matching tool use; (c) accept skills only work when
named, and route knowledge accordingly; (d) put the highest-value content in `CLAUDE.md`
despite the always-on cost, because delivery is certain there.

---

## 1. The tier model

**Enforcement strength — the ordering that matters:**
`TOOL (deterministic, exits non-zero, ZERO context — subprocess) > SKILL (verbatim when
triggered) > MEMORY (must be Read; measured 71.8% best case, 29% read zero of nine mandated)`

**Cost, measured:**

| tier | cost |
|---|---|
| `~/.claude/CLAUDE.md` | always-on, **per DISPATCH not per session** — 41,859 payers in the measured corpus |
| skill **description** | always-on, per dispatch (rides in `msg[1]`) |
| skill **body** | free until invoked, then verbatim |
| project `MEMORY.md` | **auto-injected verbatim every dispatch in that project** |
| project memory **file** | free until Read; cost is the round trip |

**1 always-on token ≈ 4,189 cost units ≈ 0.0003% of corpus. An index line breaks even at
~70 reads.** In salesagent ~43 of 168 memories clear that bar; 125 do not.

## 2. The decision procedure

| | **unprompted** (needed when nothing names it) | **prompted** (an observable cue) |
|---|---|---|
| **universal** | `~/.claude/CLAUDE.md` | user skill |
| **domain** | *(empty by construction)* | user skill, domain-scoped |
| **project** | repo `CLAUDE.md` | repo `.claude/skills/` |

The memory silo appears nowhere on purpose. **Its only defensible job is volatile project
state** — what is paused, mid-migration, needs re-verification. Not technique. Technique is
durable and durable things belong where they travel.

**Fast form — "I just learned X":**
1. True in a repo you have not seen? **No** → repo `CLAUDE.md`. Done.
2. **Yes** — is there an observable cue? → that cue's skill. No skill owns it and you can
   state the cue in one clause? → new skill.
3. No cue, needed unprompted → `~/.claude/CLAUDE.md`, **if you can say it in ≤3 lines.**
4. State that will be false in a month → the silo.
5. **Violated twice → not a memory. A hook, a test, or a lint.**

**Always SPLIT first: principle vs instance.** Most repo memories are an instance of a
general rule. Instance stays local; principle goes up. Filing the whole thing locally throws
the principle away — **that is the mechanism that stranded 241 memories.**

## 3. Routing — all 241 files

| bucket | n | effect |
|---|---|---|
| **SKILL** | **121** | content moves to skill bodies, source removed from silo |
| **PROJECT** | 66 | stays — silos shrink **241 → 66** |
| **DELETE** | 48 | 27 already verbatim in `CLAUDE.md`; 21 stale/duplicate |
| **CLAUDE.md** | 6 | **1 new line**, 5 amendments |

Exact per-file mapping: `scripts/route.py` (re-validates against the live tree).

**Key override from the first pass: `T1-UNIVERSAL ≠ CLAUDE.md`.** 115 items were marked
"universal" under a model where universal meant *promote to always-on*. Universal means
*belongs at user level*; the **skill body** is the container. Also: 10 files marked
repo-specific are Python-ecosystem-universal, stranded by a project-centric frame.

## 4. The skill set: 8 → 12 (not 14)

**Ship:** craft-context-file · craft-prompt · craft-skill · review-prompt · git-workflow ·
pr-review-method · prebid-adcp · **agent-dispatch** (new) · **writing-for-github** (new,
thinner) · **refactor-safety** (new, de-dup first)
**Generalise first:** testing-ci · test-authoring (3 rules only; 16 KB of pytest-bdd goes to
a project skill or on-demand `references/`)
**Killed:** `local-env` — 10 of 13 sources Python-flagged, 8 of 13 repo-flagged. Only 2 facts
survive and both belong in the harness skill. −453 B, no knowledge lost.
**Promoted to TOOL:** `claude-code-cost` — a script wearing a skill's clothes.

**Descriptions: strip mechanism narration.** Include only text a user might plausibly SAY.
"Scans the repo for non-derivable facts" never appears in a request — pure tax, and it
duplicates body content that is free. ~800 B of the 2,459 B proposed is this error.

**Generalise instance → principle:** `-k` → "a test selector" · `make quality` → "the shared
quality gate" · tox → one named instance of "runners that print their own success banner."

## 5. `~/.claude/CLAUDE.md`: 178 → 100 lines

3,883 → 2,118 tok **per dispatch** (−45%). Full rewrite in `reports/report-diet.md` §2.

> **CORRECTION 2026-08-02 — the routing-table cut is measured wrong.** The diet evicts the
> skill routing table as a duplicate of the `msg[1]` skills listing. Arm C of
> `EXP-skill-delivery.md` refutes this directly: the listing was present in **every** arm,
> including the one that fired 1/5. **Keep the table, rewritten imperative** (+~75 tok, the
> highest-yield 75 tokens in the file). Every other cut below stands.

Cuts that are duplicates *within the same request*: `/code-review ultra` (in the harness system prompt),
`git log @{u}..HEAD` (in the git-workflow body), and `make quality` / `./run_all_tests.sh`
(**project-specific and WRONG in most projects this file loads into**).

**Test for always-on space:** *does this rule counteract something else that is also
always-on?* The no-fan-out block earns its place because the Agent tool description and the
harness system prompt both push toward fanning out in the same context window.

## 6. Cost — REWRITTEN 2026-08-02. The directive is not free; it is the largest line item.

**Superseded by an independent blind re-derivation, 2026-08-02. Corrected figures:**

**The directive costs ~75 tok of text and induces ~2,763 tok/dispatch of body delivery** —
not 1,680. The earlier figure summed **3 of 8 skills**; the model is `Σ_skill`. The five
omitted add 2,894 B on the same denominator (prebid-adcp 1,251, review-prompt 868,
craft-prompt 353, craft-skill 52, craft-context-file 25).

| | E[body] B | tok |
|---|---:|---:|
| 8 skills, tool-using units | **7,378** | **2,763** |
| 8 skills, all live units | 7,067 | 2,647 |

**The diet does NOT pay for the directive.** Against §5's 1,765 tok/dispatch saving,
2,763 tok is **157%**. Sensitivity to the one assumption in the chain — `P(fire|topic)=1.0`,
taken from 5 embedded cells:

| P(fire\|topic) | tok | % of diet saving |
|---:|---:|---:|
| 0.6 | 1,588 | 90% |
| 0.8 | 2,117 | 120% |
| 1.0 | 2,763 | 157% |

**The diet stops covering the directive above P(fire\|topic) ≈ 0.64.**

**Both figures are FLOORS, and the reason is serious.** A mandatory routing directive routes
to **all 20 listed skills, not your 8.** The 12 bundled/plugin bodies are compiled into a
256 MB Mach-O, not on disk, and were never measured. `claude-api`'s own TRIGGER text fires on
any mention of Claude/Anthropic/Opus/Sonnet/Haiku — **present in 66.0% of tool-using task
prompts.** Nobody has costed that.

**Firing rate today: 0.10 skills/dispatch** (250 of 2,519 units, 256 invocations). The model
predicts **1.83/dispatch** under the directive — an **18x** increase.

### The tier distinction has no cost advantage. Measured, not argued.

Cache banding, confirmed on 22/22 consecutive dispatches:
- **Band A** — tool schemas + `system[0..2]` = 17,055 tok, `cache_control {scope: global}` →
  **cache READ at 0.10x** on call 0 of every dispatch.
- **Band B** — `system[3]` + `msg[0]` + `msg[1]` ≈ 11,547–11,927 tok → **cache WRITE at 2.0x
  on call 0 of EVERY dispatch**, even seconds apart. `msg[0]` carries the per-dispatch prompt,
  so nothing from `msg[0]` onward is ever reusable. **`CLAUDE.md` and the skills listing sit
  in band B. They are not amortised.**

```
always-on (band B):    κ = W + 0.10·(N−1)
body fired at call k:  κ = W + 0.10·(N−1−k)      the directive forces k = 1
```

**Per delivered byte, a body fired at turn 1 costs 96–98% of the same byte always-on.
Break-even `P_fire` is 1.02–1.06 — above 1 in every regime.** The body's only discount is one
skipped 0.10x cache read; the dominant `0.10 × N` term is paid identically by both. Confirmed
in the wire: `git.E` call 1 shows `cache_creation = 1,371` tok vs `git.C`'s 324 — the delta of
1,047 is the 1,111-tok body written at 2.0x, exactly like always-on text.

**So the entire economic advantage of "skill body" over "always-on" is the scalar `P_fire` —
and the directive exists to drive `P_fire` to 1. At `P_fire = 1` the tiers cost the same.**
§1's row *"skill body — free until invoked"* is true only of the null case the directive is
designed to eliminate.

**Pricing is not assumed.** Solving `cost = p·(2.0·cw + 0.10·cr + 5·out + in)` over 30
`result` records gives **p = $5.0000/Mtok with 0.0000% spread**. The CLAUDE.md multipliers
(1h write 2.0x, read 0.10x, output 5x) are exactly confirmed.

The old conclusion — *decide on knowledge travel and enforcement, not bytes* — still stands.
*"A rounding error"* does not, and neither does *"the diet pays for it."*

## 7. Order of operations

0. ~~Resolve §0.~~ **Done — `EXP-skill-delivery.md`. Ship the imperative routing directive
   FIRST; it is the precondition every later step depends on.**
1. Delete the 3 zero-file `MEMORY.md` indexes (−2,009 tok/dispatch in those projects). Safe.
2. Apply the `CLAUDE.md` diet + the 6 amendments — **with the routing table kept and
   rewritten imperative, not cut.** Reversible.
3. Delete the 27 already-in-CLAUDE.md memories, then the 21 stale. Backup exists.
4. Build/generalise skills; move the 121. **Only after §0.**
5. Promote `claude-code-cost` and the 3 `agent-dispatch` rules that are hooks.

## 8b. Defects found 2026-08-02 (cost pass)

- **§3 says "content moves to skill bodies." The budget says 88% of it is discarded.**
  `route.py` runs clean (241 assigned, 0 unassigned, 0 phantom) and the 121 SKILL-bound files
  total **342,921 B**. `report-structure.md:127` caps a body at **5 KB**; 8 destination skills
  × 5 KB = 40 KB. **That is 8.6× compression.** §3's language states preservation; the plan's
  own budget states loss. Neither §3 nor §8 names it.
- **`git-workflow` loses at the plan's own body budget.** Break-even needs `P* = 0.412` at
  8.6× compression; measured firing is **0.643**. It needs **13.4× compression** to break even.
  It is the only skill in the set that is worse off after the move. Move it last, or not at all.
- **Verbatim moves are off the table by 6×–13×.** Break-even crossover is 4.8%–10.5% firing;
  measured firing runs 10%–64%.
- **`references/` re-creates the tier the plan is escaping**, behind *two* gates instead of one:
  the skill must fire, then the reference must be Read. For discoverability that is strictly
  worse than an always-on index line.
- **~3,133–3,743 B/dispatch of index lines point at the 27 memories already verbatim in
  `CLAUDE.md`** — paid on the same request that already carries the content. salesagent: 2,523 B.
- **4,739 B — 46% of `CLAUDE.md` — is semantically mirrored in salesagent's `MEMORY.md`**,
  both always-on, in the same request.
- **`report-diet.md` cut `git log @{u}..HEAD` and `make quality` from `CLAUDE.md` *because*
  they live in skill bodies, pricing the body as free.** The cut is still right; the stated
  reason is void. §8's `make quality` contradiction is now a cost question, not a style one.
- **The precondition is being validated on 28% of the cost base.** Independently reproduced:
  1,911 of 2,519 units and **49,261 of 68,443 API calls are subagent = 72.0%**; every A/B cell
  is main-thread single-turn.
  **CORRECTION — the κ=3.15 vs 2.40 gap is CALL COUNT, not cache regime.** Both reproduce
  under `κ = W + 0.10(N−1)`: 2.40 = 2.0 + 0.10×(5−1) at main-thread median N=5;
  3.15 = 1.25 + 0.10×(20−1) at subagent median N=20. **At equal N the subagent multiplier is
  strictly LOWER** — its write is 1.25x (ephemeral_5m, measured 9,918/9,920 calls) against
  main-thread 2.0x (ephemeral_1h, 6,881/6,881). Reading this as "subagents make always-on
  tokens intrinsically more expensive" is backwards; they cost more only by running ~4x the
  calls. The comparison is also sensitive to which N you pick — main-thread *mean* N is 31.5,
  giving κ = 5.05, well above the subagent figure.
- **`git-workflow`'s 0.643 firing rate is the SUBAGENT-only population.** All-units is 0.578;
  main-thread is 0.375. Any break-even resting on 0.643 must name its population.
- **Subagents do not inherit the main thread's cache prefix.** Median first-call `cache_read`
  is 1,915 (main: 20,088), only 1.0% ≥15k warm, **33.2% at exactly zero.**
- **§7 step 1 independently verified to the token**: project-plugins 2,842 + prebid-github-io
  2,345 + agenticads-sim-plan 177 = **5,364 B = 2,009 tok**. Zero behavioural risk, no
  interaction with the directive. **Do it first.**

## 8. Known defects in this plan

- **`prek_pre_commit_replacement_bug` is cited twice for promotion and is marked
  `STALE as of 2026-08-01 — do not act on it`.** Promoting a memory verified dead today into
  an always-loaded skill is the most concrete defect here.
- **Two agents contradict on `make quality`:** the diet evicts it from `CLAUDE.md` as wrong-
  in-most-projects; `testing-ci`'s body keeps it.
- Router did not re-verify 9 of 11 inherited staleness claims; ~60 files routed from
  description + lead paragraph only (all to PROJECT, where a misroute is cheap).
- Six PROJECT files carry known-stale sub-claims to fix on re-index (listed in
  `reports/report-router.md` §6).
- The near-miss that nearly shipped: `feedback-timeout-is-not-an-answer` was marked a
  duplicate of a `CLAUDE.md` "Interaction section" **that does not exist** — and the
  `question_timeout_guard.sh` hook it documents is live. Deleting it would orphan the hook.
