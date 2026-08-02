All measured. Report follows.

---

# Do the findings generalize?

**Corpus.** 198 project dirs; 187 hold any `.jsonl`; **12 have ≥250 API calls**. Most of the 198 are single-shot throwaways (`ph-eval-run-*` ×105, `T-tmp-*` ×70) — real data, but one turn each. Deduped by `requestId` across main + nested subagent transcripts: **63,290 API calls, of which salesagent is 41,851 (66%)**. The independent sample is **21,439 calls across 11 other projects and 1,459 subagent transcripts in 10 of them**. Scripts: `/private/tmp/claude-501/-Users-quantum-Documents-GitHub-agenticads-sim-plan/e2367c8b-0c8b-43ae-a5d4-98ce3fbcecea/scratchpad/gen/` (`extract.py` → `rows.pkl`, then `tests.py`, `t2`–`t8`, `decay2.py`).

Headline: **traps 1 and 2 are universal, the TTL split is universal and exceptionless, trap 3 is real but salesagent is the corpus where it applies *least*, and findings 2 and 4 are wrong — one is a measurement artifact and the other has an identifiable cause that most projects don't have.**

---

## 1. The three measurement traps — the one that matters most

### Trap 1 — multiple JSONL records per API call: **HOLDS, universally**

| project | raw records | unique `requestId` | inflation |
|---|---|---|---|
| salesagent | 117,469 | 41,851 | **2.81×** |
| prebid-agt-skills | 1,059 | 291 | 3.64× |
| norbert-skills | 4,991 | 1,414 | 3.53× |
| agentic-prebid | 11,276 | 3,350 | 3.37× |
| sa-wt-1430 | 1,510 | 473 | 3.19× |
| prompt-harness | 10,247 | 3,290 | 3.11× |
| hermes-plan | 5,331 | 1,752 | 3.04× |
| sa-mainline | 7,689 | 2,593 | 2.97× |
| THIS-SESSION | 3,679 | 1,411 | 2.61× |
| EVALRUN (105 sess) | 1,137 | 474 | 2.40× |
| TMP (70 sess) | 925 | 374 | 2.47× |
| rereview-agent | 13,919 | 5,947 | 2.34× |

All 12 projects, range **2.34×–3.64×, median 3.00×**, corpus 2.83×. salesagent's 2.81× sits near the *low* end — nothing about it is special. Anyone counting JSONL records is inflated by roughly 3×.

### Trap 2 — subagents nested at `<session>/subagents/`: **HOLDS, universally, as a layout fact**

`<project>/subagents/*.jsonl` returned **0 files in all 187 directories**. Every one of the 1,459 subagent transcripts lives one level down. The *magnitude* of the miss is project-dependent:

| project | sub % of calls | sub % of cost |
|---|---|---|
| sa-wt-1430 | 85.2% | 79.1% |
| THIS-SESSION | 79.9% | 61.6% |
| **salesagent** | **76.6%** | **55.9%** |
| sa-mainline | 68.3% | 52.1% |
| rereview-agent | 67.6% | 42.6% |
| norbert-skills | 62.7% | 31.9% |
| prompt-harness | 56.3% | 38.2% |
| agentic-prebid | 55.7% | 34.9% |
| hermes-plan | 32.7% | 15.4% |
| prebid-agt-skills | 26.8% | 20.7% |
| EVALRUN / TMP / new-proj-ph | 0% | 0% |

`rereview-agent` is the extreme case by file count: **116 subagent transcripts to 4 main ones**. A top-level glob sees 3% of its files.

**Combined, the two traps do not cancel to a constant.** Naive method (every record, main files only) versus truth: `sa-wt-1430` **0.70×**, salesagent **1.30×**, prompt-harness 1.73×, agentic-prebid 1.81×, norbert-skills 2.03×, hermes-plan 2.20×, prebid-agt-skills 2.84×. The error ranges from 30% under to 184% over. There is no correction factor — you have to do it right.

### Trap 3 — `thinking` persisted as `""`: **HOLDS today, but it is not a property of the format, and salesagent is the wrong place to have found it**

- Every thinking block logged before **2026-07-14** is empty: **15,824 / 15,824 = 100.0%**.
- Every thinking block on the **current version 2.1.220** is empty: **5,734 / 5,734**, across three different projects (`rereview-agent`, `sa-mainline`, this session).
- But salesagent on v2.1.215 / 217 / 219: **14,569 blocks, 0 empty.** Full reasoning text persisted.

Corpus-wide salesagent is only **38.2%** empty; every other project is **97.6–100%**.

It is not model, not version, and not thread type. Within a *single* (model, version, day) cell the projects diverge:

```
claude-opus-4-8 v2.1.215:  salesagent=0% (n=2,654)   hermes-plan=100% (n=343)
claude-opus-4-8 v2.1.217:  salesagent=0% (n=3,161)   rereview-agent=100% (n=264)
claude-opus-4-8 v2.1.209:  salesagent=26% (n=3,453)  prompt-harness=100% (n=136)
```

Something per-project or per-session toggles it; I could not identify what from the transcripts alone — settings and env are not recorded in the JSONL. **The practical inversion matters: the `output_tokens − visible_chars/3.8` estimator was calibrated on the one corpus where reasoning is mostly *visible*. Everywhere else 100% of it is invisible and the estimator carries the whole load.**

---

## 2. The subagent `output_tokens` stub — **DOES NOT HOLD. It is a measurement artifact, and it is a fourth trap.**

This is the most consequential result, and it corrects the canonical numbers.

**Records sharing a `requestId` do *not* all carry the same `usage`.** In subagent transcripts the harness flushes a provisional usage on the first content block and the final usage on the last. Example, `rereview-agent/…/agent-a2c2276b69fc7354e.jsonl`, one `requestId` (`req_011CdS8F49zMNSBRKWfRCyjM`) written twice:

```
rec 1: output_tokens=3      blocks=[thinking]
rec 2: output_tokens=7491   blocks=[text, 15367 chars]
```

Keeping the first record — which is what "dedup by `requestId`" naturally does — reads 3.

| | API calls | multi-record | `output_tokens` differs | undercount |
|---|---|---|---|---|
| salesagent sub | 32,060 | 29,212 | 24,431 (83.6%) | **90.8%** |
| rereview-agent sub | 4,020 | 3,371 | 2,974 (88.2%) | 91.6% |
| agentic-prebid sub | 1,867 | 1,822 | 1,616 (88.7%) | 98.5% |
| prompt-harness sub | 1,851 | 1,671 | 1,461 (87.4%) | 95.3% |
| THIS-SESSION sub | 1,173 | 1,042 | 965 (92.6%) | 96.1% |
| **every main thread, 9 projects** | 18,575 | 15,471 | **0 (0.0%)** | 0.0% |

**Subagent transcripts only. Main threads: exactly zero, in every project.** `cache_read` and `cache_creation` are safe (2 of 62,422 differ) — this affects `output_tokens` alone.

**Direction is settled by physics.** `output_tokens` cannot be less than the text actually emitted:

| | visible chars | first-record sum | max-record sum | calls where output < emitted text |
|---|---|---|---|---|
| salesagent sub | 38.5M | 3,297,023 | **35,949,358** | first **87.4%** / max 11.3% |
| rereview-agent sub | 7.8M | 569,111 | **6,792,784** | first 84.3% / max 10.3% |
| agentic-prebid sub | 7.2M | 77,998 | **5,055,005** | first 98.0% / max 14.6% |

The first-record reading is impossible for 84–98% of subagent calls. The residual 10–15% under `max` is just 3.8 chars/token calibration error on `tool_use` JSON.

**FACTS.md's `subagent … 3.3M output` is 3,297,023 — the first-record sum, exactly.** Corrected:

```
salesagent  main   9,791 calls   out 25.8M   cost   506.8M   (unchanged)
salesagent  sub   32,060 calls   out 35.9M   cost   805.1M   (was 641.8M)
TOTAL                                        cost 1,311.9M   (was 1,148.6M)  +14.2%
subagent share of cost                          61.4%        (was 56%)
```

So the "median 3" is not a harness behaviour to explain. **The correct figure is that a subagent's final call emits a median of 4,808 output tokens** (salesagent 5,809; this session 7,669). Rule: **take `max(output_tokens)` per `requestId`.** For main threads first == max, so it is safe everywhere.

---

## 3. Cache TTL split — **HOLDS, universally, and it is the cleanest result in the set**

| | calls writing cache | exceptions |
|---|---|---|
| main threads | 18,575 | **0** write any `ephemeral_5m` |
| subagents | 44,602 | **13** write any `ephemeral_1h` |

The 13 exceptions are all `fork` subagents (12 hermes-plan, 1 norbert-skills) — **0.014% of subagent cache-write tokens**. Zero calls mix both TTLs. This holds identically across all 12 projects: main 100.0% `1h`, sub ~100.0% `5m`.

**Blended corpus write multiplier: 1.508×.** Assuming a flat 1.25× understates cache-write cost by **20.7%** — the brief's 20% figure, confirmed corpus-wide rather than salesagent-wide.

---

## 4. Zero prefix-cache on subagent first calls — **DOES NOT HOLD generally; the cause is custom agent definitions**

First, the salesagent claim restated non-circularly. On its first API call a subagent reads **absolute** tokens from cache:

| project | sub threads | median first-call `cache_read` | threads reading <2,000 |
|---|---|---|---|
| **salesagent** | 859 | **1,915** | **93.0%** |
| rereview-agent | 116 | 13,206 | 22.4% |
| hermes-plan | 49 | 13,222 | 28.6% |
| THIS-SESSION | 35 | 13,120 | 37.1% |
| prompt-harness | 89 | 12,006 | 40.4% |
| prebid-agt-skills | 6 | 11,362 | 16.7% |
| sa-mainline | 64 | 10,243 | 18.8% |
| sa-wt-1430 | 15 | 10,052 | 20.0% |
| agentic-prebid | 164 | 9,071 | 38.4% |
| norbert-skills | 62 | 7,828 | 19.4% |

Subagent prefix caching **works in nine of ten projects** — ~8–13k of shared harness prefix served from cache. salesagent gets 1,915.

**The within-salesagent control isolates the cause** — same repo, same `CLAUDE.md`, same period:

| agentType | n | median `cache_read` | median `cache_creation` | cold (<2k) |
|---|---|---|---|---|
| review-test-integrity | 128 | 1,915 | 52,977 | 98.4% |
| review-code-patterns | 121 | 1,915 | 54,488 | 99.2% |
| review-architecture-guards | 119 | 1,915 | 52,281 | 99.2% |
| review-spec-conformance | 112 | 0 | 54,993 | 97.3% |
| review-error-wire / bdd / security / admin-ui | 279 | 1,914–1,915 | 50,074–56,315 | 100% |
| **general-purpose** (built-in) | **76** | **9,938** | 45,954 | **42.1%** |
| **Explore** (built-in) | **24** | — | 13,585 | 62.5% |

Pooled across all projects: agents with a `.claude/agents/*.md` on disk (n=759) read a median **1,915** and are cold 99.1% of the time; built-ins (n=289) read 8,770; ad-hoc `name`-only agents (n=411) read 10,270.

The `1,915` is near-constant across seven unrelated agent types — a fixed head block. **A project-defined agent definition diverges the system prompt almost immediately, so only that first block is reusable.** Concurrency is not the cause: controlling for floor size, subagents with 3–5 simultaneous peers read a median 10,750 from cache versus 0 for solo ones.

**Price.** Median first call: review-* `53,930 cw @1.25 + 1,915 cr @0.10 = 67,604` cost units; salesagent's own `general-purpose` `45,954 + 9,938 = 58,436`. Difference **+9,970 units per dispatch × 759 = +7.6M**, ~0.6% of salesagent's corrected 1,311.9M. Real and structural, but small — the cold start is a rounding error next to the 4.27B tokens of subagent cache *reads*.

---

## 5. The decay curve — **replicates in salesagent under an independent method; UNTESTABLE elsewhere**

My first attempt (`decay.py`, "is a report's anchor echoed later?") showed *rising* survival with distance. That measure is confounded: a report delivered early has more subsequent turns in which any string can appear. I discarded it.

The clean design (`decay2.py`) holds the target fixed: score every report in a session against **the same** final write (last 40k of context travel), using only `path:line` anchors unique to that one report. Opportunity is then identical for every report in the session.

| Δ context to final write | reports | mean anchor retention |
|---|---|---|
| 25–75k | 83 | **18.8%** |
| 75–150k | 135 | 12.2% |
| 150–300k | 98 | 4.8% |
| 300k+ | 116 | **1.3%** |

Monotone, independent anchor extraction, independent matcher. **Paired sign test within salesagent: of 83 sessions with ≥2 scorable reports, the earliest-delivered report retained less than the latest in 37 and more in 11** (35 ties) — p ≈ 2×10⁻⁴. Mean 7.3% early vs 15.3% late. The consolidation report's curve is not an artifact of its matcher.

**Outside salesagent it cannot be measured.** Retention is 0.0% in every bucket for all 101 non-salesagent reports, and all 14 paired sessions tie at zero — but that is *structural, not a finding*:

| project | sessions | `path:line` anchors in the final write | sessions with any |
|---|---|---|---|
| salesagent | 142 | 1,995 | 115 |
| prompt-harness | 10 | 49 | 6 |
| sa-mainline | 9 | 50 | 4 |
| hermes-plan | 6 | 3 | 1 |
| rereview-agent | 3 | **0** | 0 |
| agentic-prebid | 3 | **0** | 0 |
| norbert-skills | 1 | **0** | 0 |

No other project produces a code-anchored consolidated artifact. The denominator is empty. **Verdict: UNTESTABLE HERE — not "does not hold".**

---

## 6. The static floor and its drift — **level: HOLDS but is project-specific. Drift: UNTESTABLE elsewhere.**

Floor = `min(input + cache_creation + cache_read)` per thread.

| project | main median | sub median |
|---|---|---|
| **salesagent** | **86,326** | **55,045** |
| sa-mainline | 60,180 | 50,371 |
| sa-wt-1430 | 60,035 | 48,488 |
| agentic-prebid | 35,975 | 17,274 |
| rereview-agent | 30,052 | 19,163 |
| hermes-plan | 29,754 | 19,313 |
| THIS-SESSION | 29,462 | 18,892 |
| prebid-agt-skills | 27,956 | 16,190 |
| prompt-harness | 27,156 | 20,380 |
| norbert-skills | 24,547 | 15,205 |
| EVALRUN / TMP | 22,304 / 22,516 | — |

The harness floor is ~22–30k main / 15–20k sub. **salesagent runs at 2.9× the main-thread floor and 2.9× the subagent floor of a comparable project** — that is `CLAUDE.md` + `tests/CLAUDE.md` + skills + agent definitions, and it is a salesagent property, not a harness constant. The salesagent family (mainline, worktree) reproduces it, confirming the repo is the cause.

**Drift cannot be tested elsewhere.** Date spans: salesagent **49 days**; sa-mainline 29 (same repo family); prebid-agt-skills 12; TMP 11; agentic-prebid 10; everything else **≤7 days**. salesagent's drift is real and reproduces (main `68,709 → 105,052`, **+5,192 tok/wk** over 7 weeks; sub `46,064 → 68,486`, **+3,203 tok/wk**), and sa-mainline agrees directionally (+2,097 / +2,260). One-week deltas from other projects are noise — hermes-plan's `+37,501/wk` is two `fork` threads inheriting 300k parent contexts.

**Evidence that would settle it:** a second project with ≥6 weeks of sustained use and a versioned `CLAUDE.md`/skills tree. It does not exist in this corpus.

---

## 7. Cost concentration — **DOES NOT HOLD as a universal shape**

Only two projects have ≥40 sessions:

| project | sessions | top 10% | top 20% | gini |
|---|---|---|---|---|
| salesagent | 159 | 35.4% | 52.7% | 0.516 |
| prompt-harness | 121 | 97.6% | 98.4% | 0.943 |
| EVALRUN | 104 | 26.7% | — | 0.473 |
| TMP | 73 | 19.8% | — | 0.292 |

The spread (0.29 → 0.94) is entirely session-mix. **91.7% of prompt-harness sessions and 100% of EVALRUN/TMP sessions cost under 1M units**; only 16.4% of salesagent's do. Restricted to substantial sessions (≥1M units), salesagent gives 133 sessions, top-decile 33.0%, gini 0.445 — and **no other project has 15 such sessions to compare against**.

"Top 10% ≈ 37%" describes a corpus of uniformly substantial sessions. It is not a law; it is what salesagent's workload looks like.

---

## What cannot be tested outside salesagent, and what would settle it

salesagent is the only project with a mature multi-lens review harness. Three findings depend on that machinery and I will not stretch them:

**Stopping rule, consolidation loss, detector false-greens — UNTESTABLE HERE.** The structural reasons, measured:
- **No panel.** salesagent has 759 dispatches across 8 fixed `review-*` types (median 6 types/session, repeated). Every other project's subagents are one-off: agentic-prebid has **114 distinct agentTypes for 164 threads**, THIS-SESSION 35 for 35, rereview-agent 86 for 116. There is no repeated instrument to measure a stopping rule against.
- **No consolidated artifact.** Zero `path:line` anchors in the final writes of rereview-agent, agentic-prebid and norbert-skills.
- **No detectors.** The 13 detectors at `.claude/rules/private/detectors/` exist only in salesagent.
- **No multi-round structure.** Only salesagent has sessions running to 8 rounds and 900k+ tokens.

**What would settle them:** a second repo running the same panel over ≥20 PRs with ≥2 review rounds each, with artifacts posted via `--body-file`, would test all three. Absent that, a within-salesagent randomised design would do better than more corpora — randomise consolidation timing (write the artifact at Δ<25k on half the rounds, at end-of-session on the other half) and measure BLOCKER retention. The decay curve is observational in both reports; the paired sign test above is the strongest control available and it is still not randomised.

**A cheaper alternative for detector false-greens specifically:** they are testable by mutation without a second corpus — feed each detector a known-bad artifact and confirm it goes red. That needs no new project.

---

## What cross-project analysis found that salesagent-only work missed

**1. Trap 4 itself.** It is present in salesagent (83.6% of subagent calls) but salesagent-only work read `3` and reported it as a finding — a "stub" to be explained. Only the contrast with `rereview-agent` (median 663, because its final calls happen to be single-record) exposed that the number was an artifact. **A pattern that is uniform inside one corpus looks like a fact; you need a corpus where it varies to see it is a bug.** This corrected salesagent's own cost by +14.2% and moved the subagent share from 56% to 61.4%.

**2. The `fork` cost mode, which salesagent has zero of.** 13 `fork` subagent threads in hermes-plan and norbert-skills start at a median context of **300,608 tokens** — versus 49,362 for every other subagent — because a fork inherits the parent's entire context. Those 13 threads cost 3.5M units, more than half of prebid-agt-skills' whole subagent history. They are also the *only* subagents in the corpus that write `ephemeral_1h` cache. A per-dispatch cost model built on salesagent would price a `fork` at ~1/6 of its real cost.

**3. Subagent-heaviness is not proportional to session count.** rereview-agent: **4 main transcripts, 116 subagent transcripts.** agentic-prebid: 3 and 164. These are projects where essentially all work is delegated, and their per-session cost is the highest in the corpus (rereview-agent median session **60.7M units** vs salesagent's 4.9M). salesagent is not the expensive shape — it is the *frequent* shape. Cost-reduction advice derived from it ("cheaper lens agents") does not transfer to a project whose exposure is three enormous delegating sessions.

**4. The floor is a project liability, not a harness cost.** Seeing 86k in isolation invites the conclusion that Claude Code has a large fixed overhead. Nine projects sitting at 22–30k show that ~56k of salesagent's main-thread floor is its own `CLAUDE.md`/skills/agents tree — and it is growing at 5,192 tokens/week. That reframes the target: the floor is the single largest *addressable* item found in any of these reports, and it is invisible without a comparison group.

**5. A caution on trap 3 that only the comparison reveals.** Every reasoning-token estimate in the salesagent work rests on a corpus where 61.8% of thinking text was actually present. Applied to any project on the current harness version — where 100% is stripped — those estimates are extrapolations, not measurements.