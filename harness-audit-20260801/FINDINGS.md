# salesagent review-harness audit — settled findings

2026-08-01/02. 8 waves, ~35 Opus subagents, 28 reports (`reports/`), raw experiments in
`experiments/`. Every number below states the method that produced it. Where a number was
corrected during the audit, the correction and its cause are recorded — the wrong values
are as useful as the right ones, because they name the traps.

**Nothing in the salesagent repo was modified.** HEAD `6881e8da4` throughout; the only
change is 23 exact-SHA fetches into `.git` (no refs created, no working-tree writes).

---

## 0. Measurement traps — verified UNIVERSAL across 12 projects / 187 dirs

Anyone measuring Claude Code cost gets these wrong by default.

| # | Trap | Effect | Scope |
|---|---|---|---|
| 1 | One API call writes MULTIPLE JSONL records (one per content block), each carrying a COPY of `usage` | **~3x inflation** (2.34–3.64x, median 3.00) | universal, all 12 projects |
| 2 | Subagent transcripts live at `<session-id>/subagents/`, NOT `<project>/subagents/` | silently misses **56–85% of all calls** | universal — `<project>/subagents/` returned 0 files in all 187 dirs |
| 3 | `thinking` blocks may persist as `""` (text stripped, tokens billed) | reasoning invisible | version/project dependent; salesagent is the ANOMALY (reasoning mostly visible), everywhere else 97.6–100% empty |
| 4 | Records sharing a `requestId` carry DIFFERENT `output_tokens` — provisional on first block, final on last | **90.8% undercount** if you keep the first | **subagents only**; main threads 0.0% affected in every project |

**Correct method:** dedupe by `requestId`, **union content blocks**, take **max** `output_tokens`
per `requestId`, drop `model == "<synthetic>"`, drop repeat `uuid` (session-resume replay).

**Cache TTL split (universal, exceptionless):** main thread 100% `ephemeral_1h` (bills **2.0x**),
subagents 100% `ephemeral_5m` (1.25x). Using 1.25x everywhere understates by ~20%.

**chars/token is not a scalar.** `tokens = content + framing`, so the ratio rises with call
size (1.40 smallest quintile → 2.47 largest). Estimator, n=820, R²=0.9964, 5-fold CV bias +0.13%:
```
vis_tok = 0.37458*text_chars + 0.39539*tool_json_chars + 69.74*n_tool_use + 17.30*n_calls
          (text 2.67 c/tok, tool JSON 2.53 c/tok)
```
Cross-checked from the input side (tool results, 100% visible, exact billing): **2.48 c/tok**.
The previously assumed 3.80 is wrong; it inflated "reasoning share" from 62.7% to 74.5%.

---

## 1. Cost model — every component MEASURED, none estimated

```
              calls    input  cache_wr  cache_rd   output  cost units
main          9,799     2.3M     85.6M     2.69B    25.8M      571.0M
subagent     32,060     2.4M    157.1M     4.27B    35.9M      805.1M
TOTAL        41,859     4.6M    242.7M     6.95B    61.7M    1,376.1M
```
Cost units = `input*1 + cache_write*(2.0 main / 1.25 sub) + cache_read*0.10 + output*5`.

- **cache read 50.5% · cache write 26.7% · output 22.4% · fresh input 0.3%**
- **Subagents: 77% of calls, 58% of cost.**
- Re-read multiplier (`cache_read / cache_write`): **28.7x**
- Blind replication (agent with no access to prior work): 41,788 calls vs 41,859 — **0.17% apart.**
  The measurement was never the unstable part; interpretation was.

---

## 2. Review quality — the lenses are NOT the problem

| Measure | Value | Method |
|---|---|---|
| Phantom citations | **0.098%** (3/3,059) | line exists at every PR commit; all 1,334 SHAs resolve |
| **Claim accuracy** | **94.5% TRUE, 0 FALSE** (n=55) | code read at the *reviewed* SHA, graded by hand |
| BLOCKER claim accuracy | **100%** (11/11) | same |
| Miss rate vs independent human | **39.6%**, CI [29.1%, 49.0%] | `git blame` opportunity denominator; all 864 rows resolve |
| Lens unique yield | 76.2% | max pairwise site-overlap 5.0% Jaccard |
| Removing any lens costs | 15–24% of panel coverage | leave-one-out |

**All 8 lenses earn their cost. Merge: none. Retire: none.** Cost-per-unique spread is only 1.5x.

**The one real claim defect is inverted from what was feared:** not a fabricated *problem* — a
fabricated *reassurance*. `full-review-pr1605-rereview-20260720.md` TI1 cites a second
corroborating oracle at `test_delivery_service_behavioral.py:340/:288` as the stated basis for
rating SHOULD-FIX instead of BLOCKER. Those lines are a circuit-breaker assert and a closing
paren; the file has **zero** HMAC code in 639 lines. The panel does not cry wolf; it
occasionally talks itself down.

---

## 3. Where the harness actually fails — all downstream of the lens

**A lens surfaces ~13 sites and emits ~3 findings** (716 lens reports, medians).

**Findings die by DISTANCE, not judgment.** Survival vs context accumulated between a report
landing and the artifact being written — **the severity ladder buys no protection at all**:

| Δcontext | BLOCKER kept | NIT kept |
|---|---|---|
| <25k | **77.0%** | 43.0% |
| 75–150k | 31.9% | 15.6% |
| 300k+ | **1.5%** | 2.0% |

Half-life ≈ **75–100k tokens**. Holds within sessions (9 of 12 monotone). Of 20 lost BLOCKERs:
45% displacement ≥150k, 30% eviction/compaction, 15% measurement artifact, **0% lost under
low context pressure**. Deliberate triage ruled out (triage language appears near dropped
BLOCKERs at 53% and near KEPT ones at 57%).

**Delivery is NOT the problem** — 758 of 759 reports arrived. 671 of 759 dispatches are async;
the report arrives as a later `<task-notification>`, not as the `Agent` tool_result.

**Identifier re-indexing destroys the audit trail.** Only **22.6%** of 1,271 lens finding-slugs
survive verbatim into any artifact; 75% of artifacts relabel to local IDs. **This is why
`disposition_ledger.py` cannot match even when its logic is fixed.**

**Severity inflation 3.7:1** (262 promotions vs 71 demotions, incl. 58 NIT→BLOCKER), measured
by joining per-finding blocks on the harness's own matcher. §4b.1 bans promotion without basis.

**The panel re-raises 10.8%** of its own unfixed sites next round. The independent human
carries 31 of the panel's abandoned findings forward, with dates.

---

## 4. The detector layer certifies the losses as clean

**12 of 13 detectors carry a CONFIRMED false-green**, proved by execution with positive and
negative controls.

- **`disposition_ledger.py:189`** — `deficit = max(0, n_findings - n_dispositions)` is a
  document-wide COUNT. 3 findings + 4 tokens clustered under one → `clean=True`.
  **Confirmed on a shipped artifact:** `full-review-pr1682-rereview-20260729.md` passes with
  15 findings / 96 tokens and an undisposed `[BLOCKER]` about a credential on the buyer wire.
- **`bump_check.py:76`** — gates on `"WARNING" in out`. **That string exists nowhere in the
  detector suite except its own test condition.** Its exit-1 arm is dead code, it discards
  `returncode`, and `harness-upgrade-spec.md:72` prescribes exactly that arm as "the drill to
  run on every adcp bump." Quoted as reassurance in 5 shipped artifacts.
- `citation_freshness.py:58` — CONTEXT must share a line with the version token; a newline
  defeats it. Proved on the detector's OWN regression corpus with a one-token edit: 1 hit → 0.
- `compound_guard_operands.py:94` — `not (a or b)` is a `UnaryOp` → 0 hits. The De Morgan form
  of the exact illusion it exists to catch is invisible.
- Plus 8 more in `reports/report-sweep9.md`.

**Live defects found by scan-set gaps (matcher fine, never looks there):**
- `salesagent/CLAUDE.md:127` says spec **3.1.0-beta.3** / `adcp==5.7.0`; actual pin is
  **3.1.1** / **6.6.0**. Git-tracked, auto-loaded every session. `citation_freshness` flags it
  immediately when pointed at it; its default roots exclude the repo root.
- `verify-spec/SKILL.md:46,78,148` directs reviewers to `dist/schemas/3.0.0-beta.3/`.
- `protocol_webhook_service.py:40` — a FIXME whose stated deletion precondition is already met.
- 143 standing `citation_freshness` hits are **~19 genuinely stale**; 124 are permanent-by-
  construction annotation debt, which is why the exit code is always 1 and agents skim it.

**5 of 8 skills cannot execute Step 1** — `cook_formula.py` absent, `bd` not installed,
`verify-spec` hardcodes `/Users/konst/...` (a collaborator's home dir).

---

## 5. Fixes DEMONSTRATED by experiment (not argued)

### Emission: the cap is not the lever — the enumeration mandate is
3 arms, identical prompts except one paragraph. Subject: 2,953-line file, **52 mechanically
enumerated ground-truth sites**. All three read **100%** of the file.

| Arm | Condition | Findings | Cites | **Recall** |
|---|---|---|---|---|
| A | cap present (charter as-is) | 5 | 32 | **27%** |
| B | **cap sentence deleted only** | 8 | 38 | **23%** |
| C | cap deleted **+ per-finding enumeration mandate** | 24 | 155 | **100%** |

**Deleting the cap is a NULL EDIT.** The entire effect is the positive instruction:
*"A finding must list every site it covers, one per line — never 'N places' prose."*

That rule **already exists** in the charter at **§4b.0** — but §4b.0 is orchestrator-scoped.
**The fix is to move it into the lens-facing §3**, not to delete §3's cap.

### Retention: the two fixes compound, neither works alone
3 arms, 8 real lens reports (95 KB), **77 ground-truth sites**.

| Arm | Sites in artifact | Sites captured anywhere |
|---|---|---|
| normal (as-is) | **7%** | 7% |
| ledger-at-receipt only | 29% | **97%** |
| ledger + no cap + enumeration | **53%** | 93% |

**7% → 53%, a 7.6x improvement — and 41% CHEAPER per site shipped** (2,293 → 1,356 chars/site).

**Prediction failed:** combined was predicted at ~97% and delivered 53%. **40 points between
capture and emission remain unexplained.** Candidates not separable from this data: the
unification instruction still collapsing sites, or the model adjudicating sites away.

---

## 6. What is NOT worth doing (each measured, not assumed)

| Rejected | Why |
|---|---|
| Relocate the 100,010 B Step-0 payload into system prompts | **Net +16.8M to +35.2M units.** 0/859 subagent first calls hit the prefix cache, so it moves cache_write→cache_write; 75.9M of residency is unavoidable; today's bill is partial only because compliance is poor |
| `review_completeness.py --index` | Ceiling **0.285%** of corpus; discards 78–88% of reviewer prose; sits on the readiness gate. (The cheap half — making `--since` required — IS worth it; it is omitted in 41% of runs and the charter calls it "not optional") |
| `ci_failure.py` | **0.054%**. A chore, not a plan item |
| Merge or retire any lens | 5% max overlap; 15–24% coverage loss each |
| Build the 41 "mechanizable" rules | Only **4 survive**, and 2 are config lines. Two prototypes produced confident wrong findings within 15 minutes, one with a 40% silent scan-set gap |
| Round-count caps on reviews | 67% of PRs get one session; re-review citation overlap is median 0%. They earn their cost. **Per-PR cost budget is the real lever** — PR #1417 alone is 9.0% of corpus; 8 PRs carry 36% |

**§5's nine mandated memory files (1.90% of corpus): CUT.** Six quality axes null or reversed;
the doctrine's effect is delivered by the always-present agent definitions instead (the
"what I could not verify" section appears in 96–99% of reports regardless of what was read).

**§5 "compliance" was never measuring charter adherence.** 95 runs read all nine in §5's order
having never loaded the charter; 39 emit all nine Reads in ONE response before any result
returns; in-order rate is *higher* without the charter (87.4% vs 82.7%). Every delivery channel
was falsified. **The nine are reconstructed, not copied** — convergent priority ordering.
Drop it as a compliance metric; charter load rate (71.8%) is the real one.

---

## 6b. WAVE 9 — four items moved from open to settled

**The §5 mystery is SOLVED, and the prior answer was backwards.** The nine files are
**copied, not reconstructed** — from `MEMORY.md`, **auto-injected verbatim** into every
agent's first user message as a `<system-reminder>` ("Contents of <memory-dir>/MEMORY.md,
user's auto-memory"). Proven on a subagent with zero tools and a custom system prompt, so it
is unconditional. salesagent's MEMORY.md is 118 lines / 19.6 KB indexing all 168 memory
files; the nine §5 files sit at lines **4, 5, 6, 8, 9, 37, 37, 53, 73** — exactly §5's order.
Method: `BUN_CONFIG_VERBOSE_FETCH=curl` dumps the assembled request body; `--debug-file`
alone shows only headers.

**Why six agents missed it: the JSONL STRIPS the injected block.** Control, same request both
ways: on-wire `msg[0]` = 11,308 B of `<system-reminder>`; its transcript = 1,878 B with
**zero** occurrences of `CLAUDE.md` or `MEMORY.md`. Every prior pass used an instrument that
structurally cannot see the channel.

**NEW COST LINE — nobody had attributed it.** MEMORY.md ≈ **7,353 tokens injected into every
one of 41,859 dispatches** = **~30.8M units, 2.2% of corpus**. Cutting the nine mandated
Step-0 *reads* does NOT remove this; only editing MEMORY.md does. Corollary: **filing a
memory in a project silo taxes every dispatch in that project forever.**

**The 28.6% never-detected band is NOT a distinct failure class — it is the same positional
effect.** Shapes carry *zero* discriminative signal (16-shape catalog, chi2=19.92, df=15,
**p=0.175**); defect class does not separate found from never-found (all 11 classes p>=0.12);
read-window membership does not either (p=0.507). What separates them is **position**: median
site line **376 (never-found) vs 189 (found), p=0.0003**. A proximity-matched null reproduces
the band exactly (p=0.14-0.79 over four null constructions). *Caveat: the original
133/37.6/33.8/28.6 could not be reproduced across 16 cluster definitions; an independent
rebuild puts the band at 36.1% (55.1% strict) — the block is real and was understated.*

**And ONE instruction defeats the position effect.** A/B recall by depth quartile of a
2,953-line file (sites span lines 48-2925):
```
ab-capped     14/52   Q1 4/13   Q2 4/17   Q3 5/11   Q4  1/11
ab-uncapped   52/52   Q1 13/13  Q2 17/17  Q3 11/11  Q4 11/11
```
Saturation, depth falloff, and the never-detected band are **one mechanism**, and the
per-finding enumeration mandate closes all three. All arms read 100% of the file — this is
not a coverage fix, it is a sweep-vs-sample fix.

**The retention experiment's ground truth was MINE and it was wrong.** `truth.json` was a
mechanical extraction of every `path:line` string in 8 lens reports — **roughly half are
PASS/cleared sites the lenses verified as FINE**, which the charter forbids reproducing
("Findings only; no praise sections"). Scored on finding anchors only, zero anchors were
silently dropped, unified away, or adjudicated away; **unification preserved 32/32 sites
across all 8 unified clusters** — that hypothesis is falsified. The 53% understated the fix.
The scorer was also too loose (no range expansion, no bare-ref resolution): 5 of the 40
"unexplained" points were measurement.

**The taxonomy replicates.** Independent blind second rater, n=150, seed 20260801, frame
verified byte-for-byte against a fresh API pull: **Cohen's kappa 0.821** [0.748, 0.888], raw
agreement 86.7%. The headline classes are the strongest: **DUP kappa 0.88, VAC kappa 0.92.**

**The human's findings are themselves correct.** 18/18 substantively true at the reviewed
SHA, zero fabricated defects; three minor errors, both count errors **undercounts**. Rule of
three: 95% upper bound ~16.7% on the false-finding rate, point estimate 0%. **The 39.6% miss
rate is not materially inflated by human error.**

---

## 6c. WAVE 10 — FOUR RECOMMENDATIONS THIS DOCUMENT DROPPED, and four overstated claims

An adversarial audit of this audit found that §§4-6 lost four recommendations in
consolidation — **the exact failure mode §3 documents.** Grep confirmed: zero occurrences of
`FINDING_TAG`, `Disposition`, `ledger-builder`, or `round-scoped` in the prior text.

### D1. `disposition_ledger.py:74` FINDING_TAG is blind to the format the corpus uses — ONE-LINE FIX, highest value in the detector set

`FINDING_TAG = re.compile(r"\[(BLOCKER|SHOULD-FIX|NIT)\b")` requires a **bracket**. But
`/full-review` Step 7 prescribes cluster headers and artifacts write `### Cluster A (BLOCKER)`
with **parentheses**. Verified by execution:

```
full-review-pr1720-20260726.md
  artifact declares : ## Summary: 1 BLOCKER / 10 SHOULD-FIX / 8 NIT / 10 FOLLOW-UP
  detector counts   : findings (severity-tagged): 0
  verdict           : "Contract met: every finding resolves to an action"   EXIT=0
```

**8 artifacts declare 161 findings the detector counts as ZERO; 3 exit 0 "Contract met"
vacuously** (`_is_clean:204` treats zero findings as clean). Corpus-wide it sees **632 of
2,750** raised findings — `deficit` is near-zero *by construction*, and only 1 of 81
artifacts shows any deficit. This is a LARGER defect than §4's count-collapse and better
evidenced. §4's `:189` finding remains true and is a separate bug; fix both.

**§3's "this is why `disposition_ledger` cannot match even when its logic is fixed" was kept
while the recommendation was discarded.** The source says both halves: fixing `FINDING_TAG`
restores the gate on 8 artifacts; it does *not* restore the slug join. Both are true.

### D2. The `Disposition` dispatch-prompt lever — one word, zero tokens

Present in 43.6% of dispatch prompts. P(lens emits a `Disposition:` line): **91.8% with vs
31.3% without = 2.9x**. Finding absent-from-artifact rate: **1.7% vs 14.6% = 8.6x reduction.**
The 91.8/31.3 link is a direct behavioural measurement, not subject to the richer-prompt
confound that affects the survival deltas.

### D3. A mechanical ledger-builder that re-reads the subagent JSONLs from disk

Prototyped: 46 rows in 0.03s. The load-bearing constraint, which the prototype satisfies by
accident and which must be stated explicitly: **it must re-read the 859 subagent transcripts
from disk at write time**, because those survive compaction and eviction while the
orchestrator's context does not.

### D4. Round-scoped consolidation — "cheaper than all of it"

Consolidate at **Δ<25k, where BLOCKER site loss is 0.0%**, instead of at 910k where one
session lost 100%. This directly exploits §3's own decay curve and is the only proposal that
addresses the **55% displacement bucket** §3 names as the dominant loss mechanism. §5
contained nothing that touched it.

### Four claims this document overstated

**(a) "Zero anchors adjudicated away … falsified" (§6b) is wrong — and commits the wave-9
error inside the wave-9 section.** The source states thinking was **100% stripped in all
three arms — 0 characters**. Every adjudication counted was *visible-text* adjudication.
**"Adjudicated away = 0" is a FLOOR, not a ceiling.** Correct wording: *not observed in
visible text; the thinking channel was empty.*

**(b) "Every delivery channel was falsified" → eight of ten.** One (`MEMORY.md`
auto-injection) is now known FALSE. A second — "0 of 95 charter-less runs quote any of 155
charter-unique phrases" — has **essentially no power**: the baseline among confirmed charter
*readers* is 1.0%, so ~1 quote was expected under the alternative. Observing 0 discriminates
nothing. The other eight rest on files-on-disk or positive transcript evidence and survive.

**(c) Wave 9 is overstated three ways.** No capture was run inside salesagent (its byte
counts were read off disk). Captures are **one version (2.1.220)** against a lens corpus
spanning **11 versions** — "injection was live in all of them" is inferred. And "copied, not
reconstructed" overcorrects: the nine sit at MEMORY.md lines 4,5,6,8,9,37,37,53,73 of 118 —
two share a line, and lines 10-36 and 38-52 are skipped. The *names* are copied (discharging
the zero-Read puzzle and 99.96% accuracy); **selecting nine of 118 and no others is still
convergent selection.** The prior answer was half right, not backwards.

**(d) "Every component MEASURED, none estimated" (§1) is contradicted by §7**, which concedes
the compaction summarization call is absent from the transcript **entirely**. At least one
class of billed call produces no JSONL record. **1,376.1M is a LOWER BOUND.** The blind
replication does not repair this — same instrument, same files, so it replicates the blind
spot rather than testing for it. **A blind replication establishes transcription fidelity,
not validity.**

*(Not affected: the cost model itself. `usage` counters are billing totals returned by the
API, so stripped CONTENT does not remove TOKENS. The MEMORY.md bytes were always inside the
1,376.1M — §6b's "NEW COST LINE" is an attribution, not an addition.)*

---

## 6d. WAVE 10 — replication, the cost nobody priced, and compaction settled

### Both flagship experiments REPLICATE on new material

**Exp 1 — enumeration mandate**, 3 new files, ground-truth rules stated mechanically, arms
verified to differ by **exactly one line**, all arms read 100% of their file, scored with the
harness's own `disposition_ledger.site_tokens`:

| subject | GT n | capped | cap-deleted | **enum mandate** |
|---|---|---|---|---|
| original | 59 | 10% / 30% | 8% / 35% | **100% / 100%** |
| s1 | 73 | 2% / 39% | 10% / 13% | **46% / 76%** |
| s2 | 37 | 2% / 48% | 0% / 2% | **97% / 100%** |
| s3 | 66 | 3% / 53% | 6% / 18% | **93% / 100%** |
| **mean** | | **4% / 42%** | **6% / 17%** | **84% / 94%** |

*(strict / listy matcher.)* **Cap-deletion remains null-or-negative on 4 files.** The enum
effect is robust to matcher choice (84→94); the capped/nocap numbers are NOT (4→42).

**Exp 2 — ledger-at-receipt**, 8 different lens reports (PR #1567), classifier stated,
36 finding anchors of 103 raw sites (same 3:1 ratio as the original's 21/77):

| arm | finding anchors | chars/anchor |
|---|---|---|
| normal | 22/36 = **61%** | 656 |
| **ledger** | **35/36 = 97%** | **691** |
| combined | 36/36 = 100% | 1,539 |

**The ledger alone reaches 97% at the same cost per anchor as doing nothing.** The last 3%
costs 2.3x per anchor.

### The enumeration mandate's cost — measured, and it changes the program

Replayed the three A/B arms with FACTS' own method (dedupe `requestId`, union blocks, max
`output_tokens`, subagent rates):

```
ab-capped    calls=14  out=15,013  units=252,293   1.00x
ab-nocap     calls=17  out=17,369  units=223,996   0.89x
ab-uncapped  calls=18  out=28,953  units=401,017   1.59x
```
Delta 148,725 units x 738 panel dispatches = **109.8M units = 8.0% of corpus**, subagent side
only; +~1.9% when the 3.08x-larger report lands in main context. Honest band **2-10%**.

**Against total savings of 7.1-10.0%** (compaction 3.0-5.9 + §5 cuts 1.90 + MEMORY.md 2.2):
**the program is cost-neutral at best — and every saving was measured while the one cost
item was not.**

### Precision: the mandate does NOT fabricate

Zero out-of-file citations across 775/978/1,112 distinct line references. Enumeration
precision 97%; all 4 apparent misses are near-variants the arm itself labelled as such.
**Adjusted precision 100%.** The price is output length (2.4-2.9x), not correctness.

### Compaction — SETTLED, and cheaper than every estimate

Captured end-to-end on the wire plus `CLAUDE_CODE_ENABLE_TELEMETRY=1
OTEL_METRICS_EXPORTER=console`:

| full-roster capture | |
|---|---|
| summarization input (fresh 1.0x) | 30,504 |
| summarization cacheRead (0.1x) | 95,666 |
| summarization output | 1,288 |
| **cost of the compaction** | **$0.140102** |
| the ordinary turn right before it | $0.200762 |

**A compaction costs LESS than one normal turn.** It runs on the *session model* (never a
cheap one), `max_tokens: 64000`, and **retains the full tool roster** — which is what
preserves the cache prefix. §7's "gross, not net" caveat is closed: net ≈ gross.

### Two more explanations falsified; the floor residual GREW

- **Tool roster is not the floor residual.** Measured: MAIN 11 tools/57,987 B; sub
  general-purpose 8/29,829; Explore 5/18,103. salesagent lenses declare 4 tools → **≤6,137
  tok, LESS than the 12,400 previously charged.** Correcting it widens the gap ~6,300 tok.
- **Found `msg[1]`** — a `role:"system"` message on every request, absent from every
  transcript: deferred-tools + agent roster + skills listing + Auto Mode = **~7,926 tok for
  salesagent vs 2,150 charged, a 3.7x undercount.** Rebuilt floor 44,789 tok; **residual
  ~10,200 tok, NOT closed.** Remaining candidates need a capture inside salesagent.
- **~25,500 B (~10,300 tok) per request rides in a channel transcripts cannot see.** But
  skill bodies and nested `CLAUDE.md` ARE recorded. Two mechanisms worth knowing: **invoking
  a skill injects the whole SKILL.md**, and **reading one file in a directory pulls in that
  directory's CLAUDE.md for the rest of the session.**
- **The injected block is byte-identical across agent types** — the ~55k-vs-~46k floor
  difference is not there either.

### Method defects in this audit's own experiments

- **Exp 1's ground-truth rule was never persisted and is not re-derivable.** No mechanical
  rule yields the published n=52; `^\s*with DeliveryPollEnv\(` yields **59**, spanning
  exactly the reported 48-2925. Re-scored under n=59 the 27%/100% reproduce — **the effect
  is real, but as filed the experiment could not be checked.**
- **Anchor tolerance was undocumented and does most of the work.** At line-exact matching the
  published headline is **28%, not 100%** (that arm anchored 43 of 59 rows at the *import*
  line 3 rows above the `with`). Any replication must state its anchor window.
- **The nocap arm's published 23% is largely range-expansion** — 3% strict; it cited ranges
  up to 361 lines wide.

### Fix #1's justification is narrower than filed

`report-ret47.md:95`: *"the ledger fix alone is sufficient for findings; the no-cap +
enumeration additions buy coverage of EVIDENCE, not of findings."* **#1 contributes nothing
to retention once #2 ships.** Its case is lens EMISSION alone (Q4 1/11 → 11/11) — real and
large, but it must be sold as that.

**And the configuration recommended was never run.** Arms are A=cap/no-mandate,
B=no-cap/no-mandate, C=no-cap+mandate. **There is no cell D = cap + mandate**, which is what
"copy §4b.0 into §3 while keeping the cap" ships. Cell D is also arithmetically
self-contradictory: §3 caps at ~5 findings with the rest as one-line `also:` entries, and its
own mandatory template is already 7 lines against its own ≤6-line cap.

**"Move §4b.0" is the wrong verb — COPY it.** Unification preserved 32/32 sites *driven by*
§4b.0; moving it out removes a control measured working.

---

## 7. Open — do not claim these are settled

- **What binds the remaining 47%** of retention after both fixes. Unexplained.
- **How a lens names 9 files it never read.** Needs the assembled system prompt
  (`claude --debug` / logging proxy). **Unreachable from transcripts** — JSONL never persists
  system prompts.
- **The 28.6% of multi-site clusters where NO site was found.** Sized, no mechanism, no
  defensible proposal. The one failure no state fix touches.
- **Compaction's own billing.** The summarization call is absent from the transcript entirely;
  every compaction saving is gross, not net.
- **`reviewer-tooling.md`'s masking-gotcha recipes.** Ungradeable by construction — a prevented
  false-green leaves no trace. Not priced in either direction; this is why they were not cut.
- **Generality of the review findings.** The measurement traps generalize (12 projects). The
  stopping rule, consolidation loss, and detector false-greens are salesagent-only —
  it is the only corpus with a mature multi-lens harness.
- Taxonomy of misses is **one grader, no second rater**.

---

## 8. Method notes that earned their place

- **Direct measurement beat careful inference twice.** Subagent output: 179.7M measured vs a
  193–229M reasoned "correction" (the original 178.7M estimate was right). The cap: three arms
  inverted a conclusion built from three waves of observation.
- **A two-arm experiment would have shipped a null edit.** The third arm is what showed
  cap-removal does nothing.
- **Every "verification" done with a looser instrument than the thing it checked produced a
  confident wrong answer.** This happened to the orchestrator 4 times (mention-vs-content grep
  x2, wrong denominator unit, content-block splitting) and to at least 4 subagents
  (basename-guesser → 15 fake phantoms; all-digit SHA → 3 fake phantom files; naive
  `file.py:NNN` → 5 false drops of 6; "does not exist" in prose → 474 fake failed reads).
  **Use the harness's own matcher, or state that you did not.**
- Agents that reported their own errors before reporting results were consistently the ones
  whose results held up.
