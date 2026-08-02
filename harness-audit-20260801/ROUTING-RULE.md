# Routing rule — where does a new fact go?

Five destinations, strongest first: **TOOL → CLAUDE.md → SKILL → repo → MEMORY.**
Run the gates in order. First YES wins. Every gate is a question you can answer by looking,
not by judging.

---

## Gate 0 — SPLIT. Always. Before anything else.

Rewrite the fact with **every proper noun replaced by its category** — repo, path, command,
version, tool, person.

- What survives and is still actionable = **the principle (P).**
- What you deleted = **the instance (I).**

**Route P and I separately. Never route the pair as one item.** Filing the whole thing where
the instance belongs throws the principle away — that is the single mechanism that stranded
241 memories in 14 silos that do not load across directories.

`-k` → *a test selector*. `make quality` → *the shared quality gate*. `tox` → *a runner that
prints its own success banner*. `git mv` → *a rename staged by the VCS*.

If nothing survives the rewrite there is no P. It is pure instance — see Gate 5.

---

## Gate 1 — TOOL. Can a program decide it, and has prose already failed?

**All five must be YES.** Any NO and it is not a tool.

| | test |
|---|---|
| **T1** | The verdict comes from bytes on disk or an exit code, with **no judgment about intent**. |
| **T2** | The input that decides the verdict is **not chosen by the party being checked**. (A sweep whose `--pattern` the checked agent supplies goes green by narrowing the regex. That is not a gate.) |
| **T3** | **Violated ≥2× *after the rule existed*.** "Has it ever happened" is satisfied by construction — every memory is written after an incident. You need non-compliance with the rule in force. |
| **T4** | **Name the wrong artifact the violation produced** — the commit, the comment, the report, the false finding. Measured non-compliance with no recorded harm is not a gate; it is evidence the rule is over-specified. (Two rules at 7% and 16% compliance were correctly rejected on T4 alone.) |
| **T5** | **False-red is affordable.** Estimate precision from the recorded cases. Below ~50%, it ships as a worklist that **always exits 0**, never as a verdict. |

**Cheapest form first.** If a permission entry, a `deny` line, an ignore line, or a git hook
produces the same enforcement, *that is the tool* — do not write a detector. Half of the
surviving tool candidates in the last audit were config lines, not code.

### SHIP GATE — a tool that cannot go red is worse than a memory, because it certifies failure as success. 12 of 13 shipped detectors were false-greens.

No tool counts as shipped until all six hold:

1. **Prove red.** Run it on an input that MUST fail; observe non-zero. A tool never observed
   red is presumed broken.
2. **Prove red on an *unmodelled* form.** One fixture written in a spelling you did **not**
   design for, taken from the corpus's own output. It exits non-zero, or it names the form as
   out of scope **in its own output**. (You cannot test your way out of an unimagined input:
   the negative cases come from the same imagination as the positives.)
3. **Exit code from a structured value, never `"TOKEN" in output`.** Propagate a child's
   `returncode`; read both streams.
4. **Print the scan set — roots, file count, base ref, resolved commit — and exit 2 on zero
   inputs.** Zero inputs is an error, never a clean verdict.
5. **Assert per item, never in aggregate.** N findings vs N dispositions across a document
   proves nothing about the pairing.
6. **Parse argv; an unknown flag exits non-zero; `--help` prints help.**

---

## Gate 2 — ARRIVAL. Could a skill possibly deliver this in time?

**If any of these three is YES → `~/.claude/CLAUDE.md`, and stop.** This is the real
discriminator. It is *not* cost: a skill body fired at turn 1 costs **96–98%** of the same
byte always-on, and break-even `P_fire` is above 1. Bytes no longer decide anything.

- **A1 — It must be true *before* the first tool call.** A branch-first rule, a permission
  boundary, a preflight. A skill fires at turn 1 at the earliest, and in 2 of 9 measured runs
  fired only *after* the first `Bash`→`Read`. A channel that arrives at your first action
  cannot govern your first action.
- **A2 — Nothing in the request will name the topic.** The rule's whole job is to fire when
  no cue is present. Skills fire on cue overlap; measured **3/28** unprompted in embedded work.
- **A3 — A consumer may be an agent with a `tools:` allowlist.** An allowlist that omits
  `Skill` strips **both** the tool and the skills listing — measured. Skills are invisible
  there; a `Read` still works, always-on still arrives.

- **A4 — It must hold on a turn where the owning skill will NOT fire.** Added 2026-08-02;
  this is the test that actually catches things. A task auditing a component with GitHub
  Actions defects routed to `testing-ci` **7/7** and `git-workflow` **0/7** — the CI-evidence
  rule sat in the body that never loaded, and landed in 3/7 answers from general competence.
  **The failure mode is routing, not decay.** Ask: is there work that needs this rule but does
  not look like this skill's domain?

**Strengthener (not required):** does something *else* that is also always-on push the other
way? A rule that counteracts the harness prompt or a tool description must sit in the same
context window as the thing it counteracts.

**Hard cap: ≤3 lines.** Longer means it is two rules. The ≤3-line gate goes always-on; the
explanation goes in the skill body the gate's own words reach.

### What Gate 2 is NOT for — measured, so the old intuitions do not apply

**Not persistence.** Within a session a fired body and `~/.claude/CLAUDE.md` sit in the same
message array, ~120 messages behind the current prompt, and **neither is refreshed**. A body
still governed the work at turn 18 with the `Skill` tool blocked, matching a fresh session
(`p = 0.0286`). There is no privileged position for always-on content. **Do not promote a rule
because it "has to last."**

**Not depth.** Routing fires per-topic at any depth measured — `craft-context-file` fired at
turn 22, 270K tokens of context, as its first tool call. A repeat of an already-loaded skill
does not re-fire, and does not need to: the body is still in the window.

**Compaction is the one real asymmetry.** A fired body is conversation history and is
**annihilated** — 0 of 19 rules retained, exact and 6-gram. `~/.claude/CLAUDE.md` survives
verbatim.

**CORRECTION 2026-08-02 — user-level and project-level `CLAUDE.md` refresh differently.**
- A **project** `CLAUDE.md` written mid-session appeared at the very next dispatch (+503 B,
  new sha, no restart). It is re-read per dispatch.
- The **user** file is not. Proven by direct inspection: a session running 4+ hours after
  `~/.claude/CLAUDE.md` changed was still injected with the **pre-edit** file — it carried a
  phrase (`"Distilled from 255 memories"`) with 0 occurrences on disk, and the old 4-row
  passive skill table instead of the live 8-row imperative one.
- It IS rebuilt at a compaction boundary (observed post-compaction, regenerated into `msg[0]`).

**Operational consequence: editing `~/.claude/CLAUDE.md` does not reach a running session.**
It lands at the next session start, or at the next compaction. Every `claude -p` measurement
gets the current file because each is a fresh session — but a long session keeps whatever it
started with, and will keep it for hours. Worse, the summary keeps *the record that the skill was
loaded* while keeping none of its content — a false green that argues against reloading. The
always-on imperative text re-fires the skill through that summary (measured 3/3 on the shipped
config, body verified absent first).

> **RESOLVED 2026-08-02 — the paragraph stays, for a different reason than it was installed.**
> Same-run LIVE-vs-FLOOR, one fixed config, four seeds, cycle entirely within each arm:
>
> | arm | turn-1 fired | post-compaction re-fired |
> |---|---|---|
> | LIVE | **4/4** | 4/4 |
> | FLOOR (paragraph removed, imperative table intact) | **2/4** | 3/4 |
>
> **Post-compaction is NOT the discriminator** — `p = 1.0`, and FLOOR's 3/4 includes a *first*
> fire from a cell that never loaded at turn 1, so it never faced the failure mode. Genuine
> re-fire denominator 2/2.
>
> **Turn-1 firing is the discriminator.** Both FLOOR misses **branched and committed real
> repo-changing git with no skill loaded** — the harm case. LIVE is 4/4 with zero variance
> across two runs; FLOOR is unstable at identical config (2/4 and 4/4, pooled 6/8).
>
> **Mechanism:** in LIVE the directive survives compaction through **two** channels — `msg[0]`
> regenerated from disk, *and* the summary quoting it verbatim. FLOOR has only one.
>
> **The rule, corrected:** an imperative paragraph AND an imperative routing table together.
> The table alone routes, but not reliably. Note `p = 1.0` at n=4 is not evidence of equality
> — best achievable is 0.0286.

---

## Gate 3 — SKILL. Is there a cue, in words a user would say?

Write the cue in **≤12 words someone would actually type.** If you cannot, go back to Gate 2.

**Then `grep -i` those words against every existing skill description.**

- **Any hit → add to that skill's BODY.** A body costs nothing until it fires. Stop here.
  This is the default and it is right most of the time.
- **No hit → new skill only if all three:** the cue is disjoint from every existing
  description; the body is ≥1 KB of real content; the description fits in ≤400 chars of
  **user-sayable text**.

**Every description is a permanent tax on every dispatch of every project** — 8 skills =
5,049 chars ≈ 1,891 tok, paid whether or not anything fires. So: no mechanism narration.
"Scans the repo for non-derivable facts" is a sentence no one says — pure tax, and it
duplicates body content that is free.

**Skills do not fire unprompted.** An imperative routing directive in `CLAUDE.md` takes
embedded-work firing from 3/28 to 14/14. Without it, Gate 3 delivers nothing.

### Three description rules, each measured 2026-08-02

**1. Give every description a `Not for …` clause naming the neighbour it loses to.** 6 of 11
skills carry one, 5 do not — **both measured false-firers are in the no-clause group**, and
both skills predicted to mis-route *do* carry one and correctly abstained. 2 events on an
11-skill cross-tab: supported, not proven, but the clause is nearly free.

**2. Constrain the OBJECT, not just the verb.** `git-workflow` fired 3/3 on *"explain what
`git rebase --onto` does — I'm not running it"* because its description was a bare verb list.
Its body is entirely about operations that **change** a repo; the description never said so.
A description that does not name its object matches every sentence containing its topic.

**3. Check what a body costs before letting it fire.** A bundled skill delivered **852,377 B
≈ 213,000 tokens** on one wrong fire — a fifth of a context window, for three incidental
mentions. Its own trigger claims any "LLM-shaped task with provider unstated." Where the
description is not yours to edit, the only lever is an always-on suppression line.

**False-fire is real but not harmful, measured:** 2/6 on genuinely ambiguous cases (95% CI
4.3–77.8%, so direction only), 0/5 miss, 0 mis-routes. Neither wrong body degraded the
answer — one was pure waste, **one measurably improved it.** Do not trade a quality gain for
a token saving.

### `references/` — the pointer's GRAMMAR is the whole variable

Measured: with a trailing noun-phrase pointer (`references/deferred.md: topic · topic`),
**0 of 13 runs opened the file.** Change only the grammar to a conditional imperative — same
file, same everything — and it goes to **3 of 3, read first.** Across 176 real production
fires: imperative procedure-bound pointers **94%** opened, trailing noun phrases **0%**.

**The mechanism:** bodies whose pointers work are *unexecutable* without the file. Bodies whose
pointers fail are complete without it — the pointer is an appendix, and appendices do not get
read. Write the pointer as **conditional** ("if the case is X, Read it first"), not
unconditional MUST — an unconditional read cost +33% and the production skills that work all
route conditionally.

**Caveat: this shows the file gets read, NOT that its contents add value.** In the same
experiment all arms — including the floor with the rule nowhere — reached the same finding.

---

## Gate 4 — SCOPE. User level or repo level?

Ask of **P**: *would this be false, or name a thing that does not exist, in a repo you have
never seen?*

- **No** → user level (`~/.claude/CLAUDE.md` if Gate 2 fired, else a user skill).
- **Yes** → repo level (repo `CLAUDE.md` if Gate 2 fired, else `.claude/skills/`).

Ask of **I**: it is always repo level, or machine level. It never travels.

---

## Gate 5 — MEMORY. Rare, and only one thing qualifies.

**Volatile project state — and you can name the event that makes it false.**

Write the expiry event *into the file* on the first line. "When #1379 merges." "When the
migration reaches L2." "When the pin passes 6.0."

- Cannot name the event → it is durable. Durable things go where they travel. Not memory.
- It is technique → not memory. Technique is durable by definition.
- No future session needs it → it is a note. Delete it.

**Default unindexed.** An index line in `MEMORY.md` is auto-injected verbatim on **every
dispatch in that project** and breaks even at ~70 reads. Most files never get there.

---

## Retirement — four triggers. Nothing here is permanent.

- **R1 — The anchor fails.** Every always-on line and every skill description carries at
  least one checkable anchor: a path, a command, a flag, a version. Re-run the anchors on any
  re-index. Fails → correct it or delete it.
  **"STALE — kept for history" inside a channel that still loads is a defect, not a
  retirement.** History goes to the backup directory; the live channel loses the line.
- **R2 — Duplicated inside one request.** The same content in two channels that both load on
  the same dispatch → delete the copy, keep the strongest tier. Check before adding: an index
  line pointing at content already verbatim in `CLAUDE.md` is paid twice on the same request.
- **R3 — A description that never gates a fire.** Its cue words appeared in N prompts and the
  body fired 0 times → the description is pure tax. Rewrite it in the user's words once; if
  it still does not fire, fold the body into a neighbouring skill and delete the description.
- **R4 — A tool that has never gone red.** No observed non-zero exit since its input format
  last changed → re-prove it on a fixture. Un-reproved → demote to a worklist (exit 0) until
  it is.

**An item whose expiry event has occurred is deleted, not annotated.**

---

## The whole thing, on one line each

```
0 SPLIT    principle vs instance — route separately, always
1 TOOL     T1 bytes · T2 input not the checked party's · T3 violated ≥2× in force
           · T4 name the wrong artifact · T5 precision ≥50%  → then the 6-item SHIP GATE
2 ARRIVAL  needed before the 1st tool call, OR no cue will appear, OR a skill-blind
           consumer → ~/.claude/CLAUDE.md, ≤3 lines
3 SKILL    cue in ≤12 sayable words → grep existing descriptions → hit = existing BODY;
           no hit = new skill only if disjoint + ≥1 KB + ≤400-char sayable description
4 SCOPE    false in a repo you've not seen? → repo level, else user level
5 MEMORY   volatile state with a named expiry event, written into the file. Else not memory.
R RETIRE   anchor fails · duplicated in one request · description never gates a fire ·
           tool never went red
```
