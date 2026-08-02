# Experiment: does knowledge in a skill actually reach the work?

> ## CORRECTIONS — adversarial re-audit, 2026-08-02. Read before quoting anything below.
>
> ### REPLICATED at n=9 per arm, 2026-08-02. Part 2 is settled.
>
> | arm | project `CLAUDE.md` | directive | original | **replication** | pooled |
> |---|---|---|---:|---:|---:|
> | C | none | none | 1/5 | **0/9** | 1/14 |
> | **F** | **present, non-routing** | **none** | 1/5 | **1/9** | **2/14** |
> | E | present, routing | yes | 5/5 | **9/9** | **14/14** |
>
> **All runs pooled: no-directive 3/28 vs directive 14/14, Fisher exact two-sided
> p = 1.29e-08.** Replication alone: C+F 1/18 vs E 9/9, p = 2.13e-06; F vs E, p = 0.000411.
> The C-vs-E replication hit `p = 4.11e-05` — exactly `2/C(18,9)`, the **permutation floor**;
> no arrangement can produce a smaller value.
>
> **Zero within-cell variance in all 6 cell×arm combinations.** Deterministic mapping: exactly
> one Skill call per arm-E run, always the correct skill (git→git-workflow, test→testing-ci,
> pr2→pr-review-method). **Arm C and arm F transcripts contain zero assistant-text or thinking
> mentions of "skill" across all 18 runs** — not a near-miss, a total absence of consideration.
> No degenerate cells: `pr2` verified dirty (` M a.txt ?? parse.py`) in all six.
>
> **Qualifications the replication surfaced:**
> - **The directive's ordering clause is violated 2/9.** `pr2.E.2` and `pr2.E.3` fired *after*
>   `Bash`→`Read`, not "before your first substantive action." The cost model's `k=1`
>   assumption does not always hold.
> - **Body cost is +37.5%, not +16.5%** (git +24.9%, test +29.8%, pr2 **+56.0%**). Do not quote
>   +16.5%.
> - **The 20% baseline is neither confirmed nor refuted.** `gitmv` — the only cell that ever
>   fired spontaneously, and the sole source of both 1/5 baselines — was not in the replication
>   set. Arm C's replicated baseline is **0/9**.
> - **Inherited design flaw:** arm E's tree carries an extra untracked `CLAUDE.md` that arm C's
>   does not, so for `pr2` the two arms review different content. **Arm F controls this** — its
>   tree carries a `CLAUDE.md` too, and it still returns 1/9.
>
> **Part 2 (the firing A/B) survives everything.** Arms C/E/F recounted from raw JSONL,
> Fisher p-values correct to 4 dp, the `--allowedTools` confound I most feared **does not
> exist** (`permissionMode=auto` and the full 32-tool init roster in all 42 cells; arm A ran
> Bash successfully despite Bash not being in its `--allowedTools` — the flag governs
> auto-approval, not availability).
>
> **Part 3 does NOT survive. Do not quote its numbers.**
> - **"Arm G lost the skills listing" is FALSE.** All three arm-G transcripts list **24
>   skills** in `system/init`, byte-identical to C and E. `--disallowedTools "Skill"` removes
>   only the *tool*. `runF.sh`'s own header says so. **The bracketing argument — "listing
>   presence contributes ≈0" — is a claim about a variable with zero variation. Retracted.**
> - The headline table (3 cells) and the "performed-only" qualification (5 cells) are
>   **computed over different cell sets**; the `+43` being "corrected" is not the table's gap.
> - **The denominator was chosen after seeing results** — 10 = the union of markers some arm
>   hit. Against the pre-registered non-LEAK pool: C 5/13, G 4/13, E 9/13, gap **+31, not +40**.
> - **T3 leaks.** 17 markers exist, not 12; T3's *regex* matches `~/.claude/CLAUDE.md` via
>   `selector`. The leak screen was run against the human label, not the scoring regex — a
>   looser instrument than the thing being checked, again.
> - Surviving from Part 3: the **`pr2` contrast is real and unambiguous** — `pr2.E` emitted six
>   `W4P2-nn` IDs with `severity: … · disposition: …`; `pr2.C` and `pr2.G` emitted none. The
>   direction (the body changes the work product) holds on that evidence alone.
>
> **"5/5 with a directive" is really 10/11 (91%).** The excluded `pr` cell was not degenerate:
> `pr.D` ran 5 tool calls, directive present, `pr-review-method` covering the task, and never
> fired. It is the only run where the directive was live, a skill applied, and nothing fired.
> *"One always-on paragraph takes that to 100%"* is **not supported.** (Excluding `pr` from the
> C-vs-E contrast is defensible — arm E never ran it — and including it would have made that
> result *stronger*: C 1/6 vs E 5/5, p = 0.0152.)
>
> **Part 1 cost figures were low by ~18%.** Correct: **20 entries** (24 registered),
> **9,951 chars ≈ 3,727 tok**, **82.8%** of `msg[1]`. Both earlier figures were undercounts —
> 8,426 broke at `claude-api`'s multi-line description, 9,033 counted entry first-lines but
> skipped the continuations. **The user-8 subtotal of 5,049 chars ≈ 1,891 tok is unchanged.**
>
> **Every "B" in Part 1 is a character count, not bytes** (`len(str)`, not `len(str.encode())`)
> — 0.3–0.6% low, and the identical mislabel class already caught once this session.
>
> **Part 4 is 4 tasks, not 5** — `adv` is the `regex` task reworded with no N counterpart.
> Rule of three on n=4 gives a 95% upper bound of **75%**, not ~60%.
>
> **Arms A and B are 4 cells each**, not 8 and 8 — the table doubles n. And this experiment
> tested **4** skills in isolated framing, not 8.
>
> **"Nothing was modified" is false.** The 42 runs created **34 new project directories** under
> `~/.claude/projects/`. No skill, `CLAUDE.md`, or settings file was altered — the substantive
> assurance holds, the sentence does not.
>
> **Cost deltas are unreliable.** `git.G` ran on a **cold cache** (`cache_read=0`, cw=24,561 vs
> a warm 17,055 prefix in C and E), so any cost comparison touching arm G is invalid
> uncorrected. `+16.5%` silently drops the `gitmv` cell — the one where C also fired.


Run 2026-08-02. Scripts and raw transcripts:
`/private/tmp/claude-501/-Users-quantum-Documents-GitHub-agenticads-sim-plan/e2367c8b-0c8b-43ae-a5d4-98ce3fbcecea/scratchpad/{wire,ab}/`
Nothing in `~/.claude` or any repo was modified. Scratch git repos only.

---

## Part 1 — what actually ships, measured on the wire

Instrument: `BUN_CONFIG_VERBOSE_FETCH=curl` (dumps the assembled request body; `--debug-file`
shows headers only). Bearer tokens redacted on capture — 0 residual `sk-ant-` hits.

One `claude -p` dispatch, run in a directory with **no project CLAUDE.md**, so everything
observed is user-level:

| block | bytes | carries |
|---|---:|---|
| `system[0..2]` | 1,357 | billing header, SDK identity, env/gitStatus |
| `system[3]` | 9,274 | main-thread harness prompt |
| **`msg[0]` role=user** | **11,341** | `<system-reminder>`: **`~/.claude/CLAUDE.md` verbatim** + MEMORY.md + userEmail + date |
| **`msg[1]` role=system** | **12,024** | deferred-tool list + agent types + **the skills listing** |
| tools | 11 | `Agent Bash Edit Read ReportFindings ScheduleWakeup **Skill** ToolSearch Workflow Write` |

**The delivery mechanism is intact.** `Skill` is in the tool roster. All 16 skill
descriptions ship in `msg[1]`, in full, on every dispatch.

**Cost of the skills listing: 8,426 B ≈ 3,156 tok per dispatch (70% of `msg[1]`).**
Your 8 are 5,049 B ≈ 1,891 tok of that:

| | B | | B |
|---|---:|---|---:|
| craft-context-file | 987 | review-prompt | 776 |
| craft-skill | 778 | craft-prompt | 641 |
| pr-review-method | 511 | testing-ci | 466 |
| git-workflow | 460 | prebid-adcp | 430 |

So the question was never "does the description arrive." It arrives, always, and it is
already paid for. The question is whether anything acts on it.

---

## Part 2 — the A/B, and the instrument trap I walked into first

**Two framings.** *Isolated*: the request IS the skill's topic. *Embedded*: the skill's
topic is a sub-step of a larger task — the shape §0's near-miss evidence describes
("14 sessions ran a mutating git verb, 0 fired").

**Three directive conditions.** none · appended system block · **a `CLAUDE.md` file**
(the `msg[0]` system-reminder — the channel a real edit would use).

| arm | framing | project `CLAUDE.md` | directive | fired |
|---|---|---|---|---:|
| A | isolated | none | none | **8/8** |
| B | isolated | none | system block | **8/8** |
| **C** | **embedded** | **none** | **none** | **1/5** |
| D | embedded | none | system block | **5/5** |
| **E** | **embedded** | **present, routing** | **yes** | **5/5** |
| **F** | **embedded** | **present, NON-routing** | **none** | **1/5** |

**Arm F is the control that makes the claim causal, and it was missing from the first
write-up of this experiment.** C vs E changed *two* things: whether a project `CLAUDE.md`
existed at all, and whether it carried the directive. Arm F holds the file present with
length-matched, same-register prose routed at nothing.

**C = F = 1/5, and the identical single cell fired in both** (`gitmv`). Merely having a
project `CLAUDE.md` does nothing. The directive text is the whole effect.

Pooling the two no-directive arms: **2/10 vs 5/5, Fisher exact two-sided p = 0.0070.**
Arm C alone against E would have been p = 0.048 — one cell from meaningless. The control
both isolates the variable and is what gives the result its power.

Directive text (arm D/E): *"SKILL ROUTING IS MANDATORY. Before your first substantive
action, check the available-skills listing. If any skill description covers any part of the
task, you MUST call the Skill tool for it first. Do not act from memory when a skill covers
the topic."* ~55 words ≈ 75 tok/dispatch.

**I measured arm A first and it said 8/8 — including all four skills PLAN.md marked
NEVER.** That reading was wrong, and wrong in the reassuring direction. A single-turn prompt
that maps onto exactly one skill is a *looser* instrument than the claim under test. The
claim was about embedded work. Embedded work answers **1/5**.

Same failure as the eval harness itself: **all 8 skills score 100% on isolated test prompts,
which is why nobody noticed they were dead.** The eval was measuring a framing that real work
never produces.

**One cell was degenerate and is excluded:** `pr` arm C/D ran against a freshly-copied clean
worktree, so there was genuinely nothing to review; both arms correctly declined. It carries
no signal either way. Re-run as `pr2` with real uncommitted changes — arm C 0, arm E 1.

**One cell fired unprompted** (`gitmv`, arm C): *"confirm the rename is actually recorded"*
sits almost verbatim on git-workflow's *"confirming a commit actually landed."* Spontaneous
firing tracks surface overlap between the sub-step's wording and the description. That is the
whole of the 20% baseline.

---

## What this settles

**§0's blocker is real and is resolved.** Skills do not fire on their own in real work — 20%.
One always-on paragraph takes that to 100% on 5/5 embedded cells, delivered through the
channel a `CLAUDE.md` edit actually uses.

**The passive routing table now in `~/.claude/CLAUDE.md` is measured insufficient.** Arm C ran
with the real user CLAUDE.md, table and all, and still fired 1/5. `"Situational depth lives in
skills that load when relevant"` + a `| Skill | Loads for |` table describes; it does not
instruct. The imperative form is what moved the number.

**PLAN.md §5 proposed deleting that table as redundant with the `msg[1]` listing.** Arm C is
the direct refutation: the listing was present in every arm, including the 20% one. Presence
is not delivery. **The table should be rewritten imperative, not cut.**

**The routing plan inverts.** "Skill bodies are free until invoked" is true, and with the
directive in place invocation is now the common case rather than the null case — so moving
121 memories into skill bodies becomes sound. It was not sound an hour ago.

---

## Part 3 — does firing change the WORK PRODUCT? Yes. (measured 2026-08-02)

Invocation is necessary, not sufficient. A skill that fires and is then ignored delivers
nothing. Measured with a 12-marker rubric of behaviors each SKILL.md prescribes, each one
first grepped against `~/.claude/CLAUDE.md` and **discarded if it leaked** — mutation-testing,
isolated-copy, and `git log @{u}..HEAD` were all thrown out as non-discriminating.

**Arm G** (new, distinct from arm F above): project `CLAUDE.md` **byte-identical to arm E**
(`diff` → IDENTICAL), same prompts, same seeding — only `--disallowedTools "Skill"` added.
Directive present, body absent.

| | markers hit |
|---|---|
| C — no directive, no body, **full listing present** | **5/10** |
| **G — directive present, body BLOCKED** | **4/10** |
| **E — directive + body** | **9/10** |

**Arm G tracks C, not E.** The directive and the file's presence do not produce the
behaviors; **the body does.** Attribution is bracketed on both sides — C had the full skills
listing and scored 5/10, G lost the listing and scored 4/10, so listing presence contributes
≈0.

**The directive was live in arm G, not ignored.** All 3 runs opened with `ToolSearch` hunting
for the blocked tool, and 2 of 3 said so outright: *"No `Skill` tool is available in this
session, so the project's mandatory skill-routing rule…"*

**Sharpest contrast** — `pr2`, same prompt, same tree: C and G both produced numbered prose
with no severity/disposition split; E produced
`W4P2-01 — parse.py:3 — severity: high · disposition: author must state the contract`.
That is `pr-review-method`'s *"split severity from disposition"* reaching the artifact.

**Two qualifications that shrink the headline:**
- **One cell REVERSED.** In `test`, E scored *lower* than C (2/3 vs 3/3) — C guarded against
  "zero tests discovered reads as green," E did not.
- **3 of E's 12 hits are "named the rule and correctly declined to apply it,"** not work
  performed. **Performed-only: C 6/14 vs E 9/14** — real, but +21 points, not +43.

**Cost of the body: +16.5%** ($1.3397 → $1.5608 over 4 cells, ≈ +$0.055/run).

## Part 4 — false-fire: 0/5, and that is a WEAK bound

5 directive runs on tasks no skill covers (non-git scratch dir, read-only/docs-only work),
including one adversarially loaded with *audit / review / verify / findings*.
**0 spurious invocations.** Directive cost when it correctly does not fire: **+6.7%**
(≈ +504 cache-write tok/run). Zero runs narrated about routing.

**By the rule of three the 95% upper bound on the true rate is ~60%.** What is measured is
that no task in this set false-fired — not that the rate is low. Genuinely *ambiguous*
tasks (half-covered by a skill) were never built.

Predicted cost of one spurious fire: `prebid-adcp` 1,057 → `craft-prompt` **4,744** tok.
Anchored empirically: `git.E − git.C` cache_creation = **+1,632** tok vs 1,477 predicted (±10%).

---

## Not tested
- **Long multi-turn sessions.** Every cell is a single-turn `claude -p`. Real sessions carry
  far more context competing with the directive. Decay over a long session is unmeasured.
- **`prebid-adcp` in embedded framing** — no cell fit the scratch repo. Isolated only.
- **The user-level file specifically.** Arm E used a *project* `CLAUDE.md`; both land in the
  same `msg[0]` system-reminder block, but I did not mutate `~/.claude/CLAUDE.md` to prove it,
  because other live sessions read that file.
- **Subagent dispatches.** All cells are main-thread. Subagents get the skills listing in
  `msg[1]` too, but no lens-style dispatch was tested.
- **False-fire rate.** No cell was designed so that firing would be *wrong*. A mandatory-check
  directive plausibly causes invocation on tasks no skill covers; that cost is unmeasured.
- n=5 embedded cells, one model, one harness version.

---

## Part 5 — multi-turn and compaction. The tier model is THREE tiers, not two. (2026-08-02)

Wire capture across one real 20-turn / 134-message session, plus explicit `/compact` and
forced auto-compaction. ~60 API requests parsed. Bytes are `len(s.encode())`.

| channel | mechanism | within a session | across compaction |
|---|---|---|---|
| `~/.claude/CLAUDE.md` (`msg[0]`) | **re-read from disk every dispatch** | verbatim, unchanged sha, T1→T20 | **survives verbatim** |
| skills listing (`msg[1]`) | **replayed from history**, not re-injected | byte-identical T1→T20 | rebuilt — but **absent for the rest of the dispatch in which auto-compaction fires** |
| fired skill body | delivered once, as conversation history | byte-stable 5,029 B over 130 messages | **0 of 19 rules retained** — exact and loose 6-gram both zero |

**`msg[0]` is regenerated, `msg[1]` is not — proven.** A project `CLAUDE.md` written between
turns 2 and 3 appeared in `msg[0]` at turn 3 (+503 B, new sha) with no restart. A skill added
at the same moment never entered `msg[1]`; it arrived as a separate 232 B `role=system` delta
at `msg[48]`. The listing survives by persistence and is rebuilt only when history is discarded.

**The failure mode is a false green.** Compaction preserves *that the skill was loaded* and
discards what it said:

> `- **Skill routing** — the mandatory git-workflow skill load as STEP 0…`
> `- No git operation was actually performed — the skill load was a procedural requirement…`

A record of compliance that suppresses the reload which would restore the content. Same shape
as the 12 false-green detectors, one tier up, and silent.

**Fix applied to `~/.claude/CLAUDE.md`:** the directive is now **re-entrant** — routing is
conditioned on *"its content is not present in this context"* rather than *"before your first
substantive action"*, and it names the compaction summary explicitly as not being the skill.

**Design rule this settles:** a rule that must be honoured at an unpredictable later time
belongs always-on — its half-life in a body is "until the first compaction", and the failure
is silent. Bodies are for procedure consumed near the load and cheap to re-load.

**Not measured:** whether the re-entrant wording actually re-fires post-compaction (proposed,
untested) · whether deleting the body changes behaviour, as opposed to being absent from the
wire · natural compaction at the real threshold (this was forced with a 40,000-token window,
which thrashed) · a session that actually exercised the skill's rules, where the summariser
would have had a *use* to preserve · subagent dispatches · n=1 session.

## Part 6 — body influence does NOT decay within a session. The promotion test was wrong.

At turn 18, with `Skill` blocked so the body could not reload, the work product matched a
fresh session where the skill fires normally.

| arm | markers /10 | on the 2 discriminating markers |
|---|---:|---|
| EARLY (turn 1, body fires) | 8 | 2/2 |
| **LATE (turn 18, body 122 msgs back, Skill BLOCKED)** | **8** | **4/4 across 2 runs** |
| CEILING (fresh session, body fires) | 8 | 2/2 |
| FLOOR (no body) | 5, 6 | **0/4** |

**LATE 4/4 vs FLOOR 0/4, Fisher two-sided p = 0.0286 — the permutation floor for this n.**
Pooled body-present 9/10 vs 0/4, p = 0.0050.

**Wire, turn 18 (145 messages):** `~/.claude/CLAUDE.md` is in `msg[0]`, **128 messages behind
the current prompt**. The turn-1 body is at `msg[5]`, verbatim, 122 behind. **Within a session
they occupy the same positional slot and neither is refreshed.** There is no privileged
position for always-on content; "decay" would have to be attentional and is not observed.
The always-on directive still routes at turn 18 — the re-fire arm called `Skill` as its first
tool call, driven by text 128 messages back.

**So the promotion test is not "must hold for a whole session" — that is free either way. It
is "must hold on a turn where the owning skill will not fire."** Persistence was never the
failure mode; **routing is**.

**Instance found and fixed.** A task auditing a component with GitHub Actions defects routed
to `testing-ci` 7/7 and `git-workflow` **0/7**; the CI-evidence rule landed 3/7, erratically,
from general competence. Promoted to `~/.claude/CLAUDE.md` beside the `git grep` rule, whose
shape it shares: an empty result set is evidence about the instrument, not about the world.

**The agent's own corrections, which shrink its claim:** M1 dropped as confounded (tracks
harness reuse, not body presence) — the pre-registered 3-marker p = 0.0022 is inflated and
must not be quoted. LATE may carry the body via its own turn-1 work rather than re-reading
`msg[5]`; this design cannot separate them. `git-workflow` fired in 0/7 arms, so two markers
carry no attribution. Only 2 of 10 pre-registered markers discriminate — five hit 7/7 because
the traps are salient enough to find without the body. **n=2 per arm: the direction is
established, the effect size is not.**

**Not tested:** compaction (zero events in all 7 transcripts — and Part 5 shows that is where
bodies actually die) · distances beyond 17 turns / 96K / 128 messages · `git-workflow` body
influence at any distance.

## Part 7 — the compaction hole is closed, and the routing-table question is finally settled

Post-compaction re-fire, body verified ABSENT on the wire before every probe. **The
load-bearing marker is binary**: `"Base directory for this skill:"` absent in the first main
request of every probe, in every parse, against 93–99% 6-gram retention in the very next
request once the skill reloaded. **The residual percentage itself is unreliable** — re-parsing
the same captures returned 4.1–4.6% where 6.3–6.8% was first reported. Final reproducible
figure: **4.1–4.6%** across all six `/compact` cells, 0.8% on the auto path; the 6.3/6.8
readings are superseded and their cause is unexplained (the one hypothesis — that repeated
redaction passes mutate the capture — was tested and falsified on identical sha256). Rest the
conclusion on the absent header and the 0–1 of 19 rule-line count, not the percentage:

| arm | `~/.claude/CLAUDE.md` | re-fire |
|---|---|---|
| NEW — imperative + re-entrancy clause | | **3/3**, `Skill` first tool call |
| OLD — imperative, pre-fix wording | | **2/2** |
| **NONE — paragraph deleted, ROUTING TABLE KEPT** | | **0/2** |

**All five compaction summaries named the skill load** — the false record of compliance was
present in every cell, and every directive-present arm re-fired straight through it. It does
not suppress the reload; **absence of an imperative paragraph does.**

**This settles the table question left open in §5 of PLAN.md.** Earlier the claim "keep the
routing table" was retracted as unsupported because no arm ran imperative-without-table. This
is the complementary arm — **table-without-imperative: 0/2 post-compaction, 1/2 at turn 1.**
The table alone is insufficient. The imperative paragraph is the load-bearing element.

**And the re-entrancy wording I shipped is NOT what fixes it.** NEW vs OLD is 3/3 vs 2/2 — no
difference detected. The wording was trimmed back accordingly, keeping only the compaction
clause, which carries information the old text did not. Adding 311 B on a mechanism argument
that the varying-only-that-clause arm then returned null on is the error this project keeps
making; recording it rather than defending it.

**Mechanism isolated on the auto-compaction path (n=1):** the post-boundary request had **no
skills listing at all** (`msg[1]` gone) — yet `~/.claude/CLAUDE.md` was regenerated into
`msg[0]` and `Skill` was still the first tool call. `msg[0]` is the routing channel; the
listing is not required for it.

**Weakness, stated:** the floor arm's second replicate is degenerate — its turn 1 never loaded
the skill, so nothing could re-fire. True re-fire floor is n=1, giving 4/4 vs 0/1,
Fisher two-sided **p = 0.2. Direction only, not significant.**

**Not tested:** OLD and NONE on the auto path · a clean single auto-compaction (this one
thrashed) · sessions longer than one turn before compacting · skills other than
`git-workflow` · whether the reloaded body changed the work product.

## Part 8 — the LIVE directive re-fires after compaction (3/3). Floor unconfirmed.

Tested against the shipped text, sha256 `3e1c94ce…`, 13,430 B — verified unchanged at start
and end of the run.

| arm | imperative in `msg[0]` | body absent on wire | re-fired | position |
|---|---|---|---|---|
| **LIVE** ×3 | yes | yes (0 hdr, 8.9–9.1% 6-gram = never-loaded baseline) | **3/3** | 1st tool call |
| FLOOR ×2 | no | yes | 2/2 | 1st, and 7th |

**Detector validated against its own positive control** in the same captures: turn-1 requests
read 8.9% overlap *before* the `Skill` call and 99.0% for every request *after* it. Wire also
confirms the LIVE arm ran the live wording (`live_tail: True`, `reentrant: False`).

**The floor is confounded and does not refute Part 7's 0/2.** To remove the prior run's
degenerate cell, turn 1 was made identical across arms and the post-compaction session
branched — which launders the directive into FLOOR through history. Seed A's summary carries
it verbatim: *"Mandatory skill routing from CLAUDE.md: `git-workflow` must be loaded before any
repo-changing git operation."* Seed B was re-cut with `/compact` under FLOOR and its summary
carries only a descriptive record — but that cell's turn-1 behaviour was still produced by an
agent reading the imperative. **It is an upper bound on the floor, not the floor.**

Secondary, n=1: FLOOR.A1 fired at **tool 7** (after the code edits, immediately before the git
work) while all four other cells fired at tool 1 — consistent with the routing *table* routing
reactively on a git trigger rather than pre-emptively. Too thin to claim.

**Open:** a fully-independent floor cycle — turn 1, compaction and probe all under FLOOR. That
is the arm that would replicate Part 7's 0/2 and it is the named biggest gap.

## Part 9 — the decisive arm. The paragraph stays; my justification for it was wrong.

Same run, one fixed config, four seeds, full cycle (turn 1 → `/compact` → probe) inside each
arm. FLOOR differs from LIVE by exactly the 5-line imperative paragraph; table and
`claude-api` guard byte-identical.

| arm | turn-1 fired | post-compaction re-fired |
|---|---|---|
| **LIVE** | **4/4** | 4/4 |
| **FLOOR** | **2/4** | 3/4 |

Post-compaction Fisher **p = 1.0000**; turn-1 **p = 0.4286**.

**Post-compaction re-firing is not the discriminator, so the reason I installed the paragraph
was wrong.** FLOOR's 3/4 contains a *first* fire — that cell never loaded at turn 1, so its
summary carried no compliance record and it never faced the failure mode. Genuine re-fire
denominator: **2/2**.

**Turn-1 firing is the discriminator, and the misses are the harm case.** Both FLOOR turn-1
misses produced byte-identical 12-tool sequences that **branched and committed real
repo-changing git with no skill loaded.** LIVE: 4/4, zero variance across two runs. FLOOR:
unstable at identical config — 2/4 here, 4/4 in the clean-floor run, pooled 6/8.

**Mechanism:** LIVE's directive survives compaction through **two** channels — `msg[0]`
regenerated from disk, and the summary quoting it verbatim (observed in 2 of 4 LIVE cells).
FLOOR has one.

**Instrument discipline worth copying:** a sixth detector string read 0 on LIVE as well as
FLOOR — the paragraph line-wraps between "skill" and "covers". Dropped before use; every
retained string was validated >0 on LIVE and 0 on FLOOR first. The Fisher implementation was
validated against three previously published values.

**`p = 1.0` at n=4 is not evidence of equality** — best achievable two-sided p at 4-vs-4 is
0.0286, and a true floor rate of 60% still yields ≥3/4 about half the time.

**Not tested:** any skill but `git-workflow` · a table-absent arm, so "the table routes" is
inferred and never isolated · auto-compaction · whether the reloaded body changed the work
product · within-cell replication (every cell n=1).

## Part 10 — the user-level `CLAUDE.md` does not refresh mid-session. Proven on this session.

**Direct evidence.** A session running 4+ hours after `~/.claude/CLAUDE.md` was rewritten was
still injected with the **pre-edit** file: its `claudeMd` block contains
`"Distilled from 255 memories across 14 project silos"` — **0 occurrences in the file on
disk** — and the old passive `| Skill | Loads for |` 4-row table rather than the live
imperative `| Load it first | When |` 8-row one. Live 13,430 B vs injected 10,368 B.

**This corrects Part 5.** That part concluded "`msg[0]` is regenerated from disk on every
dispatch," from an experiment that wrote a **project** `CLAUDE.md` into the scratch cwd and saw
it appear at the next dispatch. That behaviour is real — for project files. **The user file was
never the thing tested, and it behaves differently.**

**Refresh points for the user file, as far as measured:** session start (proven), and a
compaction boundary (observed regenerated post-compaction in Parts 7–9). **Not** on file change
mid-session.

**Consequences:**
- **Editing `~/.claude/CLAUDE.md` does not reach a running session.** It lands at the next
  session start or the next compaction.
- Every `claude -p` measurement in Parts 2–9 is unaffected — each is a fresh session and got
  whatever was on disk at that moment.
- **The installed routing table has never governed a long-running session.** The delivery chain
  is proven end-to-end only in fresh single-turn and short resumed sessions.

## Part 11 — hooks installed and proven live; memory indexes cut 41%

**Both hooks fire. Verified in situ, not against fixtures.**
- `PreToolUse` `bash_command_guard.py` (merged: zsh `$VAR:<modifier>` + `git grep -E` PCRE
  atom) **blocked a real command of mine** on its first live test, with the fix in the message.
  30 selftest checks, 0 failures; `--bogus`→2, empty stdin→2, non-Bash→0 silent.
- `PostToolUse` `askq_timeout_guard.py` **fired on a real `AskUserQuestion`** and correctly
  classified a human answer (`ANSWERED`, 0 unknown keys, drift false). **This closes the
  largest open risk** — it was unverified whether `PostToolUse` runs for that tool at all.
- The replaced guard was **never alive**: it grepped for prose that is not in a hook's stdin
  and never was. 2,580 transcripts, 4 timeouts, **0 fires** in a month.
- **`settings.json` takes effect immediately** — no session restart, unlike `~/.claude/CLAUDE.md`.

**Memory: 49,889 → 29,332 B of always-on index (−20,557, 41.2%). Zero files deleted.**

| project | before | after | saved |
|---|---:|---:|---:|
| agentic-prebid | 14,219 | 2,832 | 11,387 |
| project-plugins | 2,842 | 0 | 2,842 (stale content, claim verified false) |
| prebid-github-io | 2,345 | 0 | 2,345 (stale content, repo no longer exists) |
| github-activity-db | 1,902 | 352 | 1,550 (unique digest **moved** to a memory file) |
| salesagent | 19,633 | 18,166 | 1,467 (13 R2 lines un-indexed, files kept) |
| hermes-plan | 1,388 | 303 | 1,085 |

**Method that made it safe:** every un-index candidate was probed against the *live*
`CLAUDE.md` before its line was dropped — 13/13 confirmed, 0 kept back. Every one of
agentic-prebid's 32 lines was checked for tail content reproduced in its target file before
compressing — **0 of 32 fell below 50%**, most above 90%. `github-activity-db`'s digest was the
one case that was NOT duplicated (`file_changes`, `render_as_batch`, `UP046`, `last_synced_at`
all absent from its only file), so it was moved into a new memory file rather than compressed
away. Memory files: **241 → 242**. Dangling links: **0**.

Backups: `PREHOOKS-20260802-154226` (hooks + settings), `PREMEM-20260802-154631` (256 files).

## Part 12 — the measurement tool, and its first run

`~/.claude/hooks/harness_report.py` — reads the transcript corpus and reports whether the
harness is working. `--since 7d` default, `--all`, `--selftest`. 11 selftest checks, each
proven able to go red.

**Three design questions were settled before writing it, and all three would have produced a
wrong tool:**
1. **The injected `CLAUDE.md` is NOT recoverable from a transcript** (verified 3 ways — every
   apparent hit is my own tool output or a file I Read). Currency is therefore *inferred* from
   session-start vs mtime and labelled as such, not observed.
2. **Two fire signals with different units.** `Skill` tool_use = 283 invocations corpus-wide;
   `attributionSkill` = 37,520 records-while-active. Either alone lies; both are reported.
3. **Unit = one transcript FILE = one agent context.** 663 sessions vs 2,586 files, **74%
   subagent**. Counting per session hides three-quarters of the evidence.

**The tool caught its own instrument error on first run.** Its topic signals matched *mentions*
— `craft-context-file` read 226/247 "topic present" because the day's conversation was ABOUT
`CLAUDE.md`. Rewritten so every signal keys on a **tool_use** (a command that ran, a file that
was written). Effect: 226→4, 217→17, 223→8. Four skills have no action signal at all and now
report `no signal` rather than a fabricated denominator.

**First real run (2026-08-02, 247 agent contexts):**

| finding | value |
|---|---|
| **`references/` opened after a fire** | **0 of 57** |
| `pr-review-method` | **137% capture — over-fires**, 11 fires against 8 PR-endpoint contexts |
| `craft-skill` | **11 contexts authored a `SKILL.md`, 0 fires** |
| `testing-ci` | 47% capture, the best in the set |
| contexts with ≥1 fire | 53/247 |
| ran a stale `CLAUDE.md` | **143 of 247** |

**Do not act on `0 of 57` yet.** One day, 58% of it under a stale config, and the pointers are
conditional — the condition may simply not have arisen. The distinction is now measurable
rather than arguable, which was the point. Re-run in a week; if references stay at 0 with the
condition genuinely met, that tier is decorative and the 55 KB belongs back in memories.

Baseline snapshot: `baselines/20260802-day1.txt`.
