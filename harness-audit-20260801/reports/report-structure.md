I have what I need. Design follows.

---

# Target state and migration for the memory/skill/context tiers

## The finding that drives the design

I measured actual `Read` tool calls against memory files across 2,472 session transcripts, split into pre-audit (before 2026-08-01) and audit-window traffic so this audit's own sweeping doesn't count as usage.

**241 memory files. 8,527 pre-audit reads. The distribution is not long-tailed — it is bimodal with a dead half.**

| band | files | share of files | reads | share of reads |
|---|---|---|---|---|
| never read | **51** | 21% | 0 | 0% |
| 1–2 reads | 67 | 28% | ~90 | 1.1% |
| 3–10 | 46 | 19% | ~250 | 2.9% |
| 11–50 | 25 | 10% | ~600 | 7.0% |
| 51+ | 49 | 20% | 7,590 | 89% |

Top 9 files = **43.1%** of all reads. Top 40 = **83.8%**. The bottom 121 files — half the corpus — account for **86 reads total, 1.0%**.

And the top 9 are not the 9 most useful memories. They are exactly the nine files named by path in the salesagent review charter's §5 Step-0 list (MEMORY.md lines 4, 5, 6, 8, 9, 37, 37, 53, 73 — matching FINDINGS §6b). **43% of all memory traffic is one hardcoded list, not retrieval.** Remove the mandate and the read curve collapses to a corpus where ~40 files carry everything.

**The structural bug this exposes:** a memory file's *content* is free until read, but its *index line* is injected verbatim into every dispatch. So a low-value memory is not free — it is the worst available trade. You pay always-on for the pointer and pay again for the content. 33% of all MEMORY.md bytes (16,449 B) point at files read ≤2 times ever. Another 5,364 B across three indexes point at **zero files** — those silos contain no memory files at all, and two of the three are already self-labeled `STALE as of 2026-08-01`.

Two reachability facts that reframe the problem as worse than "cross-project":

- **197 project directories, 17 have a memory silo.** A new directory starts with zero reachability by construction.
- **Silos are keyed by path, so worktrees fragment them.** salesagent's 169 memories do not load in `salesagent-mainline` or `salesagent-pr-1430`. 12 sessions ran in those directories with zero of the 169 available. Knowledge does not travel *within a single project*.

### The unit that lets anyone price a line

From the audit's own attribution (MEMORY.md = 7,353 tok → ~30.8M units over 41,859 dispatches):

**1 always-on token ≈ 4,189 cost units ≈ 0.0003% of the 1,376.1M corpus.** So 1,000 always-on tokens ≈ 4.19M units ≈ 0.30% of corpus.

Applied to an index line (~150 chars ≈ 56 tok ≈ 235K units) against a memory Read (~3,940 B mean + 70 tok framing, ~10 in-dispatch re-reads ≈ 3,500 units):

**An index line breaks even at roughly 70 reads.** In salesagent, ~43 of 168 memories clear that bar. 125 do not. *(Order-of-magnitude; assumes mean file size and ~10 re-reads per dispatch.)*

That number is useless at write time — a new memory has zero reads. So the rule below uses a proxy the author can actually evaluate.

---

## 1. The decision procedure

Two questions, asked in this order. They are independent because the tiers are priced on different axes: **scope** picks the container, **trigger** picks always-on vs. on-demand.

**Q1 — Where is this true?** → `universal` / `domain` (an external system: a protocol, an API, a tool) / `project`

**Q2 — What summons it?** → **unprompted** (I need it even when nothing in the task names it) or **prompted** (an observable cue in the task summons it)

|  | **unprompted** | **prompted** |
|---|---|---|
| **universal** | `~/.claude/CLAUDE.md` | user skill |
| **domain** | *(empty by construction)* | user skill, domain-scoped |
| **project** | repo `CLAUDE.md` | repo `.claude/skills/` |

The domain × unprompted cell is empty **structurally**: if the fact is about AdCP, then AdCP appearing in the task *is* the cue. There is no such thing as a domain fact you need when the domain is absent. That result matters — it means there are exactly two always-on surfaces and both are CLAUDE.md-class.

**Where does `~/.claude/projects/<p>/memory/` sit? Nowhere in that table, on purpose.**

Memory has exactly one property skills lack: it is repo-external and agent-writable mid-session, so it can hold things you must not commit to someone else's repo. Its defensible remaining job is **volatile project state** — what is paused, what is mid-migration, what needs re-verification. Not technique. Technique is durable and durable things belong where they travel.

**The existing type field already encodes the routing.** Reusing it as the decision procedure means the rule is applied at the moment the frontmatter is written:

| type | count | share | destination under the new rule |
|---|---|---|---|
| `feedback` | 131 | 54% | **skill body, or CLAUDE.md — not the silo** |
| `reference` | 44 | 18% | domain skill, or repo `CLAUDE.md` |
| `project` | 43 | 18% | silo — **iff volatile state**; else a skill |
| `user` | 3 | 1% | **retire the type**; CLAUDE.md already has this section |

**54% of the corpus is a type that structurally belongs elsewhere.** That single line is the migration.

### The fast form

> *"I just learned X — where does it go?"*
>
> 1. **Would this be true in a repo I haven't seen?** No → repo `CLAUDE.md`, or repo `.claude/skills/` if it has a cue. Done.
> 2. **Yes. Is there an observable cue that would make me want it?** ("I'm about to run git", "a test passed suspiciously", "I'm about to spawn agents") → that cue's skill. If no skill owns the cue and you can state the cue in one clause, that's a new skill. Done.
> 3. **No cue — I need it unprompted.** → `~/.claude/CLAUDE.md`, if you can say it in ≤3 lines. If you can't, it isn't a rule yet.
> 4. **None of the above, and it's state that will be false in a month** → the silo.
> 5. **It's a lesson you've now violated twice** → not a memory. A hook, a test, or a lint. (Your own rule: `soft memory < turn instruction < CLAUDE.md < a mechanical gate that FAILS`.)

Step 5 is load-bearing. A meaningful slice of the 131 `feedback` files are second and third restatements of a rule that had already failed — restating is what you do when the gate is missing.

---

## 2. Skills: ten, and the constraint is cue-disjointness

**Recommendation: 8 → 10 user skills. Hard ceiling ~15. Growth past 10 goes into `references/` under an existing skill, never a new description.**

The measured marginal cost of a skill is its description: **1,876 tok / 8 = 235 tok each**, always-on, every call, every project. (My independent measurement of the description text reproduced the given 1,876 exactly, so this instrument is verified rather than assumed.) Bodies are free until invoked — 2,165 B to 11,506 B, costing nothing until the trigger fires.

**Token budget is not the binding constraint.** The routing layer (CLAUDE.md 3,883 + descriptions 1,876 = 5,759 tok) is 12.9% of the audit's rebuilt 44,789-tok per-request floor. Holding it at ≤15% allows ~17 skills. The real constraint is that **a skill fires on its description alone**, and two overlapping descriptions mean the model picks one and silently misses the other. So skills must partition on **disjoint observable cues**, not on topic. I can enumerate about 10–12 genuinely distinct cues in this corpus. Past that, new descriptions buy misrouting.

### The decomposition

**Keep, unchanged (4)** — these already partition cleanly on cues and their descriptions are correctly written as trigger specs, not summaries:

| skill | cue |
|---|---|
| `git-workflow` | running git/gh; ambiguous result; unexpectedly empty grep |
| `pr-review-method` | reviewing a PR; judging whether feedback is addressed |
| `testing-ci` | proving a test/CI signal is real; suspicious pass |
| `prebid-adcp` | AdCP/Prebid protocol behavior |

**Add (2)** — both pull weight *out* of CLAUDE.md, which is the point:

| skill | cue | source |
|---|---|---|
| **`agent-dispatch`** | about to spawn a subagent, fan out, or run a swarm | CLAUDE.md L41–69 (preflight, concurrency, worktree isolation, report retrieval, output scrutiny) + ~6 silo memories |
| **`harness-cost`** | measuring Claude Code cost; auditing transcripts/JSONL | CLAUDE.md L128–146 (the four traps + the pipeline + pricing) |

**Leave alone (4)** — `craft-context-file`, `craft-prompt`, `craft-skill`, `review-prompt`.

One observation to flag without acting on it: those four consume **1,164 tok — 62% of the entire always-on skill budget** — for one topic family, and roughly 40% of that text is negative routing ("Do NOT use for X, use Y"). Four skills that must each explain what the other three are for is the signature of a boundary the author already fought. Collapsing them behind one `craft` router would recover ~900 tok always-on. **I am not recommending it in this migration** — they are well-formed, unrelated to the memory problem, and touching them is scope creep with real trigger-regression risk. It is a separate decision and should be made on its own evidence.

### The rule that makes descriptions work

**Put the hazard in the description; put the method in the body.**

The description is always-on and its only job is to make you load the skill — so it must name the *symptom you would actually observe*, not the topic. `testing-ci` and `git-workflow` already do this ("when a grep came back unexpectedly empty", "when a suite passed suspiciously"). This is what solves the otherwise-fatal objection to `harness-cost`: if you don't know the four traps exist, you don't know to load the skill. Naming them in the description ("one API call writes multiple JSONL records; subagent transcripts live one level down") carries the *existence* of the hazard always-on at ~235 tok, while the 900-tok method stays free.

**Body budget: ≤5 KB.** Skills are free until invoked, which tempts dumping. But a 12 KB body firing on 20% of dispatches costs more than the CLAUDE.md line it replaced. `craft-prompt` at 11,506 B is already over; depth belongs in `references/` that the body points at.

---

## 3. What `MEMORY.md` should be

It is injected verbatim into every dispatch in that project and it is the *only* memory cost you cannot avoid by not reading. Today: 15 files, 49,316 B ≈ **18,470 tok**, of which 33% indexes files read ≤2 times and 5,364 B indexes nothing at all.

**Target: ≤25 lines, ≤2,048 B (~767 tok). Enforced by a hook, not a rule.**

salesagent goes 118 lines → ~20. That is a 90% cut on the single largest attributed line item in the audit.

**What earns a line — exactly two things:**

1. **A live-state pointer.** Something paused, mid-flight, or needing re-verification — the class a skill genuinely cannot hold because it changes. *(`flask_to_fastapi_migration_v2` — PAUSED 2026-06-11, verify currency on resume.)*
2. **A trap with no natural cue.** You would not go looking, and missing it costs a session. **These must name the symptom, not the topic** — not "agentdb notes" but "agent-db pass ≠ fresh-CI pass". The symptom is what makes it recognizable in the moment; the topic is what makes it invisible.

Nothing else. Not technique (skill), not preference (CLAUDE.md), not a completed project.

**Keep the header instruction.** salesagent's is already correct and does real work: *"Recall ≠ enforcement. READ the topic file first. Memory is point-in-time — verify against current code."* Three lines that prevent the index being treated as knowledge.

**Should low-value memories exist as files with no index line?**

Yes — and it should be the default for everything below the bar. The file is free; the index line is not. Unindexed retention is cost-free.

But I'll be straight about what that means: **unindexed is functionally archived.** They remain greppable, but nothing prompts the grep, so in practice they will not be read again. "Keep as an unindexed file" is a deletion with a paper trail, not a retention strategy. Calling it retention is the comfortable answer and it's wrong.

That makes the real choice for every below-bar memory binary: **promote the lesson into a skill, or accept it is archived.** Forcing that choice at write time is precisely what the byte cap does.

---

## 4. Steady-state discipline: two hooks, not two rules

The task's framing is right and your own CLAUDE.md already states the ladder: `soft memory < turn instruction < CLAUDE.md < a mechanical gate that FAILS`. The 118-line index exists because nothing ever said no. So the discipline must be a `PostToolUse` hook — the mechanism already in use in `settings.json` for `AskUserQuestion`.

**Gate 1 — the byte cap. This is the load-bearing one.**

```
PostToolUse, matcher: Write|Edit
  if path matches ~/.claude/projects/*/memory/MEMORY.md and size > 2048:
      block, message: "MEMORY.md is over its 2,048 B cap (injected into EVERY dispatch
      in this project). Evict a line before adding one: which existing line is now
      technique that belongs in a skill?"
```

This makes the index *physically incapable* of growing back to 19 KB. Growth requires eviction, and eviction forces the promote-or-archive decision at write time instead of never. That is structure doing the work the model was failing to do.

**Gate 2 — the routing nudge, at the moment of the wrong action.**

```
PostToolUse, matcher: Write
  if path matches ~/.claude/projects/*/memory/*.md:
      reject if frontmatter type ∉ {feedback, reference, project}   # `user` retired
      if type ∈ {feedback, reference}:
          warn: "feedback/reference memories are usually universal. If this is true in a
          repo you haven't seen, it belongs in ~/.claude/CLAUDE.md or a skill — the silo
          loads in this directory only, and not in this project's worktrees."
```

Fires exactly when a `feedback` memory — the 54% category — is being written to the place it shouldn't go. Not a reminder; an interception.

**The third mechanism is the byte cap's side effect and it's the real one.** Once MEMORY.md is capped and the index is the only reachability path, writing to a silo becomes *visibly* a dead end. The path of least resistance becomes the skill. You do not need the model to remember the policy; you need the wrong action to feel wrong.

No quarterly reap. A reap is a rule, and rules decay — that is how 241 files happened.

---

## 5. Migration: seven steps, one irreversible, and it's optional

`~/.claude` is **not a git repo**, so reversibility comes from a snapshot. Precedent exists: `backups/memory-and-harness-20260801-122750/`.

**Step 0 — snapshot + baseline.** *Reversible: this IS the reversal.*
Copy `CLAUDE.md`, `skills/`, and all `projects/*/memory/` to `backups/pre-migration-<date>/`. Record the four numbers that will be compared after:

```bash
# the instrument — Read tool calls, NOT filename mentions
find ~/.claude/projects -name '*.jsonl' -mtime -90 -print0 \
  | xargs -0 grep -hoE '"file_path":"[^"]*/memory/[^"]*\.md"' \
  | sed 's|.*/memory/||; s|"$||' | sort | uniq -c | sort -rn
```
Baseline: 8,527 reads / 241 files / 51 never-read · MEMORY.md 49,316 B · CLAUDE.md 178 lines · descriptions 1,876 tok.

Use this exact command, not a filename grep. A mention-grep returns 1,621 hits on `MEMORY.md` alone and inflates every count — FINDINGS §8's most-repeated failure, and the one I hit on my first pass here.

**Step 1 — additive only.** *Fully reversible.*
Write `agent-dispatch` and `harness-cost`. **Cut nothing yet.** Cost at this point is deliberately **+470 tok**, so Step 3's cut is provably attributable.
*Verify:* both appear in the skill listing; descriptions parse.

**Step 2 — the canary. This is the gate.** *Nothing has been deleted; failure costs nothing.*
Pick 10 memories spanning the read distribution — 3 from the top 40, 4 from the 3–10 band, 3 never-read. For each, write a one-line task that *should* summon the covering skill, and run it. Ten short dispatches.

**If the skill does not fire, the description is wrong — fix the description, not the memory.** This is the only test that catches a bad trigger *before* the content becomes unreachable, and it is why no deletion happens before it passes.

**Step 3 — CLAUDE.md diet.** *Reversible via snapshot.*
Move dispatch mechanics (L41–69) and cost traps (L128–146) into the two new skills. **Keep the decisions in CLAUDE.md** — they must fire before the model decides to dispatch, which is before any skill would load:

> Default is a SINGLE pass, ZERO spawned agents. Cap 3–4 concurrent. Each agent is real money. **Load `agent-dispatch` before the first spawn.**

Roughly 6 lines stay, ~35 leave. *Verify:* 178 → ~125 lines; a diff shows every removed line has a home in a skill body. That diff is the deliverable — not the line count.

**Step 4 — MEMORY.md diet. The step that pays.** *Reversible; memory files are untouched, only the index.*
salesagent (19,633 B) and agentic-prebid (14,219 B) first — **68% of all index bytes**. Then delete the three zero-file indexes outright (5,364 B pointing at nothing, two already self-labeled STALE).
*Verify:* each file under 2,048 B; every dropped line's target is either covered by a skill or consciously accepted as archived.

**Step 5 — edit the charter BEFORE deleting anything.** *Reversible.*
Remove the §5 nine-file Step-0 mandate from the salesagent review charter. FINDINGS §6 already justifies this independently (six quality axes null or reversed; the doctrine's effect is delivered by the agent definitions instead).

**Order matters here and getting it backwards is the one way to break something.** Those nine files drive 3,676 reads. Delete the files first and every charter Step-0 read fails; edit the charter first and the reads simply stop.

*Verify — and this is a genuine experiment:* re-run the Step-0 instrument a week later. Reads of those nine should drop toward zero **with no change in review quality**. That is the proof that the mandate, not utility, drove 43% of all memory traffic.

**Step 6 — install the gates.** *Reversible: delete two settings.json entries.*
Both hooks from §4. *Verify:* attempt a 3 KB MEMORY.md write and confirm it blocks; write a `type: feedback` memory and confirm the warning appears.

**Step 7 — delete migrated memory files.** *IRREVERSIBLE.*

**My recommendation: don't.** Once unindexed they cost nothing, deletion buys nothing measurable, and it is the only step you cannot walk back. Leave them as an archive against the case where a lesson turns out to be missing. **All of the value is in Steps 1–6.**

---

## 6. What could go wrong

**R1 — A lesson becomes unreachable because its skill never fires.** The real risk, and the reason Step 2 exists. A memory that was read explicitly now depends entirely on a description matching a cue.

*Detection:* the paired before/after. Memory reads should fall to ~0 (expected — files are unindexed) **and skill invocations should rise on the matching cues**. Skill bodies *are* recorded in transcripts (FINDINGS §6d), unlike the injected MEMORY.md block, so this is directly observable — grep for a distinctive phrase from each SKILL.md body across the following week's sessions. A skill with zero invocations in a week where its cue plainly occurred is a broken description, and the fix is the description.

**R2 — A lesson with no cue at all.** Some memories are pure unknown-unknowns: `reference_reload_captures_active_mock` (never mix `tests/unit` and `tests/integration` in one pytest process — `importlib.reload` under a patch bakes the mock in permanently and negative tests then pass vacuously). Nothing observable precedes the damage.

These cannot go in a skill. They go to CLAUDE.md, repo `CLAUDE.md`, or — better — **a mechanical gate**. If a lesson has no cue and isn't universal enough for CLAUDE.md, that is the signal it should be a hook or a test. This is Step 5 of the decision procedure and it is where the genuinely dangerous memories should land.

**R3 — Skill body bloat.** Bodies feel free, so they grow. A 12 KB body firing on 20% of dispatches costs more than the CLAUDE.md line it replaced. Mitigation: ≤5 KB bodies, depth in `references/`.

**R4 — The canary passes on probes but fails in the wild**, because a probe written by the person who wrote the skill uses the skill's own vocabulary. Mitigation: write the 10 probes **from the original memory file's text**, before re-reading the skill description. Weak but honest; this is the residual risk and I'd rather name it than paper over it.

**R5 — Worktree fragmentation.** Not a risk — a **fix**. Skills are user-level and follow you into every directory. salesagent's worktree sessions currently reach 0 of 169 memories; post-migration they reach every migrated lesson. This is the largest single reachability gain and it is invisible in any token count.

---

## 7. Honest cost/benefit

### Per-dispatch always-on, before

| | salesagent | median silo project | new project |
|---|---|---|---|
| `~/.claude/CLAUDE.md` | 3,883 | 3,883 | 3,883 |
| skill descriptions | 1,876 | 1,876 | 1,876 |
| project `MEMORY.md` | 7,353 | ~375 | 0 |
| repo `CLAUDE.md` | 12,966 | 0–5,000 | 0 |
| **total** | **26,078** | **~6,134** | **5,759** |

### Change

| item | Δ tok/dispatch | scope |
|---|---|---|
| CLAUDE.md → 2 skills (−1,173 out, +470 desc) | **−703** | every project |
| …offset: skill bodies when they fire (~20% × 940; ~1% × 900) | +197 | every project |
| MEMORY.md diet — salesagent | **−6,586** | salesagent |
| MEMORY.md diet — agentic-prebid | **−4,559** | agentic-prebid |
| three zero-file indexes deleted | −66 to −1,064 | 3 projects |
| ten remaining silos | −100 to −400 each | those projects |

**Net: −506 tok/dispatch everywhere, −7,092 in salesagent, −5,065 in agentic-prebid.**

At 4,189 units per always-on token, corpus-scale: **≈ −30M to −33M units ≈ −2.2% to −2.4% of a 1,376.1M-unit corpus.**

### So: does this save money?

**Barely, and that is not the case for doing it.**

2.2% is about a fifth of the audit's own total savings program (7.1–10.0%), and that program was already measured **cost-neutral at best** against the enumeration mandate's 2–10%. Anyone selling this migration on token savings is selling the wrong thing. The savings are also **concentrated in two projects** — salesagent and agentic-prebid hold 68% of index bytes and the overwhelming majority of dispatch volume. A project with a 1 KB index saves almost nothing and shouldn't be touched for cost reasons.

**The case is reachability, and it is a different order of magnitude:**

- A lesson in a silo is reachable in **1 of 197** project directories — and measurably not in its own project's worktrees.
- A lesson in a user skill is reachable in **197 of 197**, including directories that do not exist yet.
- **51 files have never been read.** 118 (49%) have been read ≤2 times. Those are lessons that were learned, written down, and never came back. That is the actual loss, and no token count shows it.

**Reachability is the whole point, and cost-neutral would have been fine.** That it also removes ~2% is a bonus, not the justification.

**One thing that is not neutral and deserves its own line:** CLAUDE.md is at **178 of its own 200-line budget** (the ceiling `craft-context-file` enforces). It has ~22 lines of headroom for every universal lesson you will ever learn. Step 3 returns it to ~125 — **75 lines of headroom, a 3.4x increase**. Every future universal lesson currently has nowhere to go except a silo, which is exactly the mechanism that produced 241 stranded files. Restoring headroom is what stops the next 241.

---

## Assumptions I am stating rather than hiding

1. **4,189 units per always-on token** is derived from the audit's salesagent figure (7,353 tok → 30.8M units / 41,859 dispatches) and applied to other projects proportionally to dispatch volume. Smaller projects have fewer dispatches, so their MEMORY.md savings are worth proportionally less. This is why I attribute the savings almost entirely to two projects.
2. **Skill-body fire rates (20% for `agent-dispatch`, 1% for `harness-cost`)** are my estimates, not measurements. If `agent-dispatch` fires on 50% of dispatches it is roughly break-even on cost and justified only by CLAUDE.md headroom. Another agent may be producing a real number; substitute it.
3. **~2.67 chars/token** for always-on text, per the audit's input-side cross-check. My independent measurement of skill descriptions reproduced the stated 1,876 tok exactly, so this is verified for this surface, not assumed.
4. **The ~70-read break-even for an index line** assumes the 3,940 B mean file size and ~10 in-dispatch re-reads. It is order-of-magnitude. It is a sanity check on the index bar, not the basis for any individual keep/drop call — those use the two qualitative criteria in §3.

## What I did not verify

- I did not run the canary. Steps 1–2 are designed but untested, and R4 (probe vocabulary contamination) is unmitigated.
- I did not test either hook. `PostToolUse` with a `matcher` is confirmed working in `settings.json` for `AskUserQuestion`, but I have not confirmed that a `PostToolUse` hook can **block** a `Write` on this harness version — if it can only warn, Gate 1 degrades from a mechanical gate to a loud rule, which is materially weaker and would need `PreToolUse` instead. **Confirm this before relying on Step 6.**
- Read counts cover the last 90 days of transcripts only. Memory files older than that may have earlier reads I cannot see, which would move files out of the never-read band. The direction of that error is toward *understating* usage.
- I did not measure repo-level `CLAUDE.md` content for overlap with `~/.claude/CLAUDE.md`. salesagent's is 34,620 B — 3.3x the user file — and duplication there would be a larger line item than anything in this design. That is a separate audit and I would run it next.

**Files:** measurement artifacts in `/private/tmp/claude-501/-Users-quantum-Documents-GitHub-agenticads-sim-plan/e2367c8b-0c8b-43ae-a5d4-98ce3fbcecea/scratchpad/` — `pre_joined.txt` (241 files × pre-audit read counts, the baseline for Step 0), `never.txt` (the 51), `reads_pre.txt` / `reads_audit.txt` (the pre/during split).