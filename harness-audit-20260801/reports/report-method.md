All six quantities pinned and reproducible. Writing up.

---

# Canonical numbers

Corpus: `/Users/quantum/.claude/projects/-Users-quantum-Documents-ComputedChaos-salesagent` — 159 main + 859 subagent transcripts. Consolidated script: **`/private/tmp/claude-501/-Users-quantum-Documents-GitHub-agenticads-sim-plan/e2367c8b-0c8b-43ae-a5d4-98ce3fbcecea/scratchpad/pin/pin_all.py`** (reproduces every row below in ~40s).

| # | quantity | **canonical** | method | band |
|---|---|---|---|---|
| 1 | lens dispatches | **759** | `agentType ∈ 8 review-* types` from `*.meta.json` | exact |
| 1b | all subagents / main-dispatched | **859 / 851** | sidecar count / `Agent` tool_use in main | exact |
| 2 | charter load rate | **71.8%** (545/759) | file-H1 marker in a `tool_result` | 71.7–71.8% measurement; **65.1–78.5%** as an estimate |
| 2b | reviewer-tooling load rate | **50.5%** (383/759) | same | 50.5–50.6% / 43.0–57.9% |
| 3 | §5 all-nine compliance | **39.9%** (303/759) | 9 distinct `Read`s of the §5 paths | **39.9–41.2%** meas.; 34.2–45.6% est. |
| 3b | §5 read-zero | **29.0%** (220/759) | same | 27.5–29.0% |
| 3c | §5 file-level | **52.7%** (3,597/6,831) | same | 52.7–54.2% |
| 4 | detectors | **13** | `ls detectors/*.py` | exact |
| 5 | Bash calls, corpus | **38,451** | unique `tool_use` ids, main+subagent | exact |
| 5b | Bash calls, main only | **7,391** | unique `tool_use` ids | exact |
| 6 | per-call floor, lens | **54,901** median | `min(input+cache_write+cache_read)` per thread | drifts +2,639 tok/wk |
| 6b | per-call floor, main | **86,743** median | same | 68,709 → 105,052 over corpus |

## Why the values differed

**Lens dispatches — 759.** Four independent methods agree exactly: meta.json `agentType`, main-transcript `subagent_type`, literal grep of `"subagent_type":"review-*"`, and dedup by `(session, description)`. The join is perfect: 859 sidecars ↔ 859 `Agent` tool_use records, **zero orphans in either direction**; the 8-record gap between 859 and 851 is subagents dispatched from inside another subagent (none are lenses).

**`agentType` from `*.meta.json` is authoritative.** `description` is disproved as an identifier — 92 real lens dispatches have no "review" in their description and 6 non-lens ones do (673 / 694 / 765 depending on the regex). 738 and 756 do not reproduce under any method I could construct; they are transcription errors, not measurements. The true denominator depends on the question: **759** lens runs, **120** sessions that ran a panel, **260** fan-out turns (dispatches sharing a `requestId`).

**"301"** is a subsample, and a biased one — its charter rate (89%) and tooling rate (72%) both sit above the corpus truth.

**Charter — the whole disputed family is one bug: counting mentions, not content.** Detection variants over the same 759 runs:

| detector | rate |
|---|---|
| `"Reviewer Charter"` (file H1 — content only) | **71.8%** ← truth |
| `"review-charter.md"` anywhere | 78.8% ← **the "79%"** |
| `"charter §"` anywhere | 95.3% |
| `"charter"` anywhere | 99.5% |

The charter's *name* appears in the dispatch prompt (70.5% of runs), in all 8 agent definitions, and in the agent's own prose. **Of the 214 runs that never loaded the charter, 196 (91.6%) still cite it — identical to the 91.4% citation rate among runs that did load it.** Citation carries zero information about reading, which is the harness's own "citing ≠ reading" rule failing in exactly the way it warns about.

The **72%** is right (71.7%). The **73%** is the `step0=True` subset (72.3%). The reviewer-tooling **72%** is a marker collision: `"masking-gotcha"` appears three times in the charter (`review-charter.md:33,39,149`), so that marker fires on a charter read — it yields 71.9% against a truth of 50.5%.

**Detectors — 13.** Not a method difference: the 3,422-line figure FACTS cites alongside "12" is the sum over all **13** files, so the same listing contained 13. It is a miscount.

**Bash — all four numbers are real and measure different things.** Main: 7,475 JSONL *records*, **7,391 unique tool_use ids**. The 84-record gap is entirely session `1912d5d4` (identical `uuid` and `requestId`, written twice at different file offsets) — a post-compaction transcript replay, not extra calls. Corpus: 38,535 records / **38,451 unique ids**. Zero id overlap between main and subagent files. Use unique ids.

**Floor — the "27k" is a category error.** It is harness-anatomy's Step-0 *document volume* (100,010 B ≈ 26,318 tok an agent is told to read), not a per-call prefix. The other values are the same estimator at different scopes/dates: **77–85k** is a 4-session main-thread sample that matches the mid-July period (79,142–87,865); **55k/86k** are corpus medians. Both reproduce.

## Charter/Step-0: bounds, and what the defect actually is

**The measurement band is ±0.1pp, which is unusual and load-bearing.** I checked every leakage channel the brief named:

- partial reads (`offset`/`limit`): **0**
- `Read` results flagged `is_error`: **0**
- truncation losing the marker (Read logged, content absent): **0 of 544**
- charter content inlined in the dispatch prompt: **0**
- arrival via `cat`/relative path: **1**

Path-based (544) and content-based (545) agree. **Lower bound 71.7%, upper bound 71.8%.** Neither is more defensible — they are the same number.

**The real uncertainty is sampling, and it is large.** Behavior clusters hard by session: ICC = 0.64, design effect 4.4. **61 of 120 sessions read the charter in 100% of their lens runs; 23 read it in 0%.** The honest interval for "the harness in general" is **65.1%–78.5%**, not the naive 68.6–75.0%. This is a per-session orchestrator-template property, not per-agent noise.

**The CORRECTNESS claim needs restating.** Decomposing the 28.2%:

| | runs | share |
|---|---|---|
| prompt named the charter, agent read it | 487 | 64.2% |
| prompt named it, agent **skipped** it | 48 | 6.3% |
| prompt silent, agent read anyway | 58 | 7.6% |
| prompt silent, agent skipped | 166 | 21.9% |

Compliance is **91.0% when the dispatch prompt restates the path** and **25.9% when it does not**. The standing instruction is always present — all 8 definitions carry the Step-0 block — but it does essentially no work; the dispatch-prompt restatement does all of it.

And the agents are not disobedient. **When a dispatch prompt names specific memory files, compliance is 314/314 across all 89 such runs — 100%, zero exceptions.** The variance is in what the orchestrator asks for, not in whether agents comply. "A large fraction of the panel runs without its operating rules" is true; "the agents ignore their rules" is not.

**§5 is a genuine finding and survives scrutiny.** 255 of the 303 all-nine runs read the nine **in the order §5 lists them** — that is §5-driven behavior, not an incidental byproduct of a broad memory sweep (they read a median of 15 memory files: the 9 plus ~6 agent-specific). And §5's list exists in exactly one place: **no lens definition names any of the nine**, so the list is discoverable only by reading the charter.

Two things I could not explain: 95 runs read all nine in order having never loaded the charter, and §5 all-nine compliance is *slightly higher* among runs that skipped the charter (44.4% vs 38.2%). The dispatch prompts for those runs say "do your charter + catalog Step-0 reads" without paths. The list is evidently reaching the model by some route I cannot see in the transcripts.

## What I could not measure

- **The 89%/301 subset is not reconstructible.** I bounded the method class that produces it (every value >71.8% is mention-counting) but cannot reproduce the exact figure.
- **Floor composition is not recoverable by regression.** `usage` reports totals only. Fitting `floor ~ agent-def + prompt + week` gives a dispatch-prompt coefficient of 4.09 (physically must be ~1.0), R²=0.21 — it is absorbing harness drift, not measuring composition. I did not report an intercept from it.
- What *is* clean is a **paired within-session comparison**: in the 9 sessions that dispatched both an `Explore` and a lens, the lens floor exceeds the Explore floor by a median of **32,667 tokens** (range 31,803–36,689 — remarkably stable across the corpus). That delta is the measurable harness-controlled part of the floor.
- **Two markers have minor contamination** (`feedback-truth-over-optimism`, `feedback-verify-before-asserting` also appear in `crash_forensics_check_user_scope_first.md`), affecting 7 of 759 runs — inside the reported §5 band.
- **Compaction does not corrupt the floor estimator** (verified: all 5 compacted sessions show normal 68–78k minima), but `<synthetic>` records with zero usage and no `requestId` do — 71 corpus-wide. Any floor script must filter both.