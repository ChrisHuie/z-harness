Done. Repo clean, corpus uncontaminated (2,474 files, unchanged), 0 residual secrets, skills directory untouched.

## Headline: the descriptions are not the problem, and the plan's main remedy targets a variable already at ceiling

**4 of 8 user-level skills have never been invoked. All 8 have a 100% miss rate in real work. And all 8 score 100% hit / 0% false-fire on isolated prompts.** Those three facts together say the failure is not trigger wording — it is that real work never presents as an isolated prompt.

## Part 1 — Invocation census

Corpus: 2,474 JSONL files, 340,256 records, 95,006 unique `tool_use` blocks, 2,458 sessions, 2026-06-12 → 2026-08-02 (7.1 weeks). Unioned by `tool_use.id` (finer than requestId — a requestId split across records contributes all blocks). 227 `Skill` calls total across 13 skill names.

| skill | invocations | sessions | period |
|---|---|---|---|
| review-prompt | 94 | 93 | 07-14 → 07-15 |
| craft-prompt | 44 | 44 | 07-14 → 07-16 |
| craft-context-file | 5 | 5 | 07-14 |
| craft-skill | 3 | 3 | 07-14 |
| **git-workflow** | **0** | — | never |
| **pr-review-method** | **0** | — | never |
| **prebid-adcp** | **0** | — | never |
| **testing-ci** | **0** | — | never |

Two findings the raw count hides:

- **91% of all 146 invocations (133) came from the skills' own eval harness** (`ph-eval-run-*` / `T/tmp.*` working directories). The remaining 13 were all inside a `prompt-harness` checkout. **No user-level skill has ever fired in a project that was not its own workshop.**
- **The last invocation of any user-level skill was 2026-07-16T00:10Z — 17 days before the corpus ends.**

Caveat I have to state plainly: git-workflow, prebid-adcp, testing-ci and pr-review-method were installed 2026-08-01 16:30–16:32 local (`~/.claude/skills/<n>/SKILL.md` mtimes, single files, no `.ph-installed` marker). Their zero is over a **13.4-hour** window, not 7 weeks. The craft-* four carry `.ph-installed` markers dated 2026-07-15 17:47, which is a *re-install* time — invocations predate it, so that timestamp bounds "definitely installed since," not "first installed."

## Part 2 — Near-miss: 100% on every surface definition I tried

Denominators restricted to sessions starting after install; my own session excluded; sessions whose only match was the literal skill name (meta-discussion) dropped.

**Operational four** — 78 post-install sessions (24 main, 54 subagent), all in `agenticads-sim-plan`:

| skill | surface (what the description claims) | sessions | fired | miss |
|---|---|---|---|---|
| git-workflow | ran a mutating/plumbing `git`/`gh` verb | 14 | 0 | 100% |
| git-workflow | ran `git grep` (named in the description) | 5 | 0 | 100% |
| git-workflow | ran `git stash` (named in the description) | 1 | 0 | 100% |
| prebid-adcp | AdCP + spec-version / error-code / SDK-mapping | 7 | 0 | 100% |
| testing-ci | mutation / empty-red-set / `-k` selector work | 8 | 0 | 100% |
| pr-review-method | PR endpoints, `reviewThreads`, `issues/N/comments` | 6 | 0 | 100% |

**craft-\* four** — 939 sessions since 2026-07-16:

| skill | surface | sessions | fired | miss |
|---|---|---|---|---|
| craft-context-file / review-prompt | mentions CLAUDE.md / AGENTS.md / GEMINI.md | 186 | 0 | 100% |
| craft-skill | SKILL.md / agent skill / slash command | 53 | 0 | 100% |
| craft-prompt | write a prompt / system prompt / agent instructions | 18 | 0 | 100% |

The 186 are spread across 17 distinct days, 152 of them predating this audit — genuine ongoing work, not this audit talking about itself. I verified the prebid-adcp surface by hand: `agent-adetector-sweep-9` was analyzing an `adcp` version-bump detector, squarely the "SDK-to-spec version mapping" trigger, with zero skill-name contamination.

**Two corrections to my own numbers.** I initially counted 26 git sessions; most were read-only forensics (`git show` 177 uses, `git log` 30) — an audit reading history, not doing repo mechanics. 14 is the defensible number. And I nearly reported that `~/.claude/CLAUDE.md`'s routing table (lines 7–12, naming exactly the four zero-fire skills) was in force during the miss window — it was written at 21:35 local, *five hours after* the skills. Only 16 sessions post-date it; 5 ran git; 0 fired. Direction holds, n is small.

## Part 3 — Live testing: the triggers work perfectly

40 cases (8 skills × 3 should-fire + 2 should-not), `claude -p`, read-only toolset, `--no-session-persistence`, in a non-git scratch dir. Mechanical assertion on `tool_use.name == "Skill"`.

**24/24 POS fired the correct skill. 0/16 NEG false-fired.** Perfect on every skill, including all four that have never fired in production.

Better still, the four anti-trigger cases each routed to the correct *neighbour*: "tell me what's wrong with this system prompt" → `review-prompt` (not craft-prompt); "write me a new system prompt" → `craft-prompt` (not review-prompt); "critique this SKILL.md" and "review our CLAUDE.md" → `review-prompt`. The disambiguation clauses that `report-skillaudit` proposes trimming are demonstrably working.

**So why 0/78 in real work?** I tested the obvious hypothesis. Same core ask, wrapped in a realistic orchestrator envelope (Step-0 read list + constraints + deliverable spec):

| | bare | enveloped |
|---|---|---|
| git-workflow | fired | fired |
| testing-ci | fired | **NOFIRE** |
| pr-review-method | fired | **NOFIRE** |
| prebid-adcp | fired | **NOFIRE** |

**4/4 bare → 1/4 enveloped.** Supporting mechanism: `Skill` was the **first tool call in 10/10** bare fires; in the one envelope that fired it was 4th of 6, after the Step-0 reads. Skill selection is effectively a turn-1 decision, and a mandatory-read directive occupies turn 1. **56% of post-install subagent prompts open with exactly such a directive** — including the one that launched me. The house convention that `report-skillaudit` proposes codifying into `agent-dispatch` ("open every prompt with a mandatory Step 0 read list") is the same construct that suppresses skill firing.

**I falsified my own instrument.** Re-running the g1 prompt with `Skill` in `--disallowedTools`: 0 fires; control: 1. The assertion has a working red state.

**Body injection confirmed on the wire.** The transcript records only a 29-byte `Launching skill: git-workflow` stub — you cannot tell from a transcript whether the body arrived. Under `BUN_CONFIG_VERBOSE_FETCH=curl`, all 36 substantive SKILL.md lines are present in the assembled request (31 matched naively; the 5 misses all contain quotes or backslashes — JSON-escape artifacts). Redacted, 0 residual `sk-ant-*`.

Cost: $9.78 for 40 cases (~$0.24 each).

## Part 4 — A verification method

**What a positive control is.** A bare, well-targeted user request that provably fires the skill. Necessary, and my data proves it is *not sufficient* — all 8 skills pass it while 4 have never fired in anger. So the gate needs three tiers:

- **Tier 1 — bare POS/NEG.** 3 should-fire, 2 should-not per skill. Catches description regressions, name collisions, an unparsed or uninstalled skill. Cheap, deterministic.
- **Tier 2 — ENV.** The same ask wrapped in a Step-0 task envelope. **This is the tier that matters and the one nobody runs.** Every skill in this audit passes Tier 1; three of four fail Tier 2.
- **Tier 3 — corpus miss-rate monitor.** Weekly re-run of the Part-2 scan: surface sessions, fires, miss rate per skill. A skill at 100% miss over N≥20 surface sessions is dead regardless of what Tier 1 says.

**The assertion must be mechanical, not model-graded.** `Skill(skill="X")` either appears in the stream or it does not. The existing prompt-harness evals grade `expected_behavior` prose with an LLM rubric (`packages/eval/src/grade.ts:2` — "an llm-rubric judge scores each expected_behavior criterion PASS/PARTIAL/FAIL"). For trigger verification that is an unnecessary judge in the loop and reintroduces exactly the false-green pathology this audit documented.

**Falsifying the gate itself.** `--mutant` adds `Skill` to `--disallowedTools`; every POS/ENV case must go red. If they stay green the assertion is not reading what it claims to. Run it whenever the harness changes. This is testing-ci's own doctrine applied to the instrument.

**What a regression looks like:** a POS case stops firing (a description edit broke a lexical hook); a NEG case starts firing (over-broad edit); an ENV case that used to fire stops; Tier-3 miss rate rises or fires go to zero over a window with non-zero surface.

Runnable now, extends to 13–14 skills by adding rows:
- `/private/tmp/claude-501/-Users-quantum-Documents-GitHub-agenticads-sim-plan/e2367c8b-0c8b-43ae-a5d4-98ce3fbcecea/scratchpad/trig/skill-trigger-check.sh` — the gate, with `--mutant`; refuses to run with cwd inside a git repo
- `.../trig/cases.tsv` — 44 cases (40 POS/NEG + 4 ENV)
- `.../trig/final_miss.py`, `.../trig/parse_skill.py` — Tier 3
- `.../trig/score.py` — scorer (guards against scoring a still-streaming file; that race gave me one spurious miss before I fixed it)

Budget for 14 skills: 70 bare + 14 ENV ≈ $20/run, ~90 min sequential, trivially parallelizable.

## What this means for the 8 → 13-14 plan

`report-skillaudit` spends its central recommendation on description rewrites (−974 B) ranked by an unmeasured "trigger reliability" column. Measured, that column is flat: **every skill is at 100/0 on bare prompts.** Description quality is not the binding constraint. Trimming the anti-trigger clauses risks the disambiguation I measured working, for no gain on a variable already at ceiling.

Adding 6 skills without Tier 2 or Tier 3 adds 6 more skills to a set with a 100% measured miss rate. The two changes with evidence behind them: get skill consultation into the turn-1 slot that Step-0 read lists currently occupy, and gate every new skill on an ENV case before it ships.

Also worth knowing: the four operational skills exist **only** as single files in `~/.claude/skills/` — no source repo, no evals, no version control, no backup. The craft-* four have an eval suite, baselines, and a runner in `prompt-harness`.

## What I could not test

- **13.4 hours** is a short window for the operational four, and per-skill n is 6–14. The direction is unambiguous (0 fires on every surface) but a week would firm it up.
- All 78 post-install sessions come from **one audit in one repo** — not a representative workload.
- Live tests used a 4-tool roster and an empty cwd; real sessions carry 15+ tools and a project CLAUDE.md. That biases *toward* firing, so the ENV non-fires are conservative and the bare hit rates are optimistic.
- Several craft-* runs hit `error_max_budget_usd` mid-generation. The Skill decision happens at turn 1, before the cap, so trigger measurement is unaffected — but those transcripts are truncated.
- I could not determine when the four operational skills were *first* authored, or what `~/.claude/CLAUDE.md` said before 2026-08-01 21:35 (`~/.claude` is not a git repo).
- ENV suppression is n=4. It is a clean causal signal, not a rate.

Side effects: none. Repo clean, `~/.claude/skills/` untouched, corpus unchanged at 2,474 files (`--no-session-persistence` kept test runs out of it), 0 residual secrets. All artifacts under `/private/tmp/claude-501/-Users-quantum-Documents-GitHub-agenticads-sim-plan/e2367c8b-0c8b-43ae-a5d4-98ce3fbcecea/scratchpad/trig/`.