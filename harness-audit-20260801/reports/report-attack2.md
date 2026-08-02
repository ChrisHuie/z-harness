I ran the numbers rather than reading them. Here is what survives.

---

# Pass 2 is right about compaction, wrong about everything it ranked highest, and it never ran the one test that decides the correctness question

All figures below are from scripts I ran over the 691 MB corpus at `/Users/quantum/.claude/projects/-Users-quantum-Documents-ComputedChaos-salesagent/`, deduped by `requestId`, subagents included. Cost units = `input + 1.25·cache_write + 0.10·cache_read + 5·output`. Corpus = 1,148.5M units.

---

## 1. Item #3 (`autoCompactWindow`) — the cost case survives and gets *bigger*. The risk case is somewhere nobody looked.

The 4.7-8.9% figure was computed as `excess above cap × 0.10`, which models context as *clamped* at the cap forever. That is not what compaction does — it resets to the floor and regrows. I simulated the real behavior: replay each main thread's per-call context deltas, fire an event when the simulated context crosses the cap, reset to `floor + 3,500` (measured summary size 3.0k-4.1k tok), continue.

```
cap 200,000: 286 events/124 sessions | gross 146.4M | net +5.6% .. +11.8%
cap 300,000: 124 events/ 90 sessions | gross 105.0M | net +4.5% .. +8.6%
cap 400,000:  63 events/ 48 sessions | gross  71.3M | net +3.0% .. +5.9%
cap 985,000:   6 events/  5 sessions | gross  -9.4M | net -1.6% .. -0.9%   (should be ~0 → ±1% model error)
```

Net is after charging compaction's own cost. Two components, one of which nobody priced:

**(a) The cache-reset burst is measurable and it is in the transcript.** Every one of the 6 real events is followed by a full prefix re-write:

```
1834ae34  last-before cw=190    | first-after cw=47,291
1912d5d4  last-before cw=3,768  | first-after cw=49,168
44a9ffb6  last-before cw=3,290  | first-after cw=51,641
670a5ade  last-before cw=3,570  | first-after cw=65,958
b5382f8e  last-before cw=2,846  | first-after cw=52,749
```

~53k tokens × 1.25 = ~66k units per event. At 124 events that is ~8.2M units. Both prior reports missed this and it is the one part of compaction's cost that *is* recorded.

**(b) The summarization call is not in the transcript, but it is priceable.** The last pre-boundary call shows `cache_read=946,139` — the conversation prefix is cached at that instant, so the summarizer reads it at 0.10, not writes it at 1.25. The low end (6.3M at a 300k cap) is the right end, not a floor. That makes my net closer to **+8.6% than +4.5%** — larger than the plan claims.

**My re-work hypothesis was wrong, and I'll say so plainly.** I expected a lower window to make things worse via re-derivation. Measured repeats of pre-boundary tool calls after each real boundary:

| session | post-boundary tool calls | repeated from before |
|---|---|---|
| 1834ae34 | 41 | 0% |
| b5382f8e | 40 | 0% |
| 44a9ffb6 | 106 | 6% |
| 670a5ade | 147 | 11% |
| 1912d5d4 | 215 | 41% (66k tok re-fetched) |

Monotone in runway. But under a 300k cap the median post-event runway is **29 calls** (mean 32, p90 62) versus **96 calls** today, and only **1 of 124** events lands in the ≥100-call regime where re-work was 11-41%. More events, each shallower. Re-derivation is not the objection.

**The objection is review-specific, and it is severe.** I checked what the summarizer actually preserves:

| session | charter refs | §-refs | severity labels | lens names |
|---|---|---|---|---|
| 1834ae34 (PR #1399 review) | 0 | 0 | **0** | 0 |
| 1912d5d4 | 0 | 0 | **0** | 0 |
| 44a9ffb6 | 0 | 0 | 8 | 0 |
| 670a5ade (PR #1669) | 0 | 1 | **0** | 12 |
| b5382f8e (#1 costliest, multi-round review) | 4 | 5 | 2 | 8 |

**Three of five compaction summaries preserve zero severity-labelled findings. Four of five preserve zero charter reference.** The finding ledger does not survive compaction.

And at a 300k cap it fires in the wrong place: of 84 lens-running sessions that would cross 300k, **15 cross it before their last lens dispatch**. `1834ae34` crosses at call 18 while its dispatches run from call 7 to call 40 — compaction lands mid-panel. That is `review-charter.md:108` (§4b.0) — "two agents each raised one shard... unsynthesized, both were dropped" — mechanized as a scheduled event.

Also unbudgeted: **124 events × 86-246s measured duration = 3.0-8.5 hours of added wall clock** across the corpus.

**Verdict: 400-500k is safe and captures 3.0-5.9%. 300k is not, unless compaction is forbidden between the first and last lens dispatch of a round, or the summarizer is made review-aware.** The plan's number is if anything conservative; its risk model is absent.

---

## 2. Item #2 (relocate the 100,010 B Step-0 payload) — STOP. It is net cost-*increasing*, and the reliability premise is contradicted by this corpus.

The reliability framing means "it costs more" is a repricing, not a refutation. So I did both.

### It costs more, under every placement

```
lens dispatches 761 | median 32 calls | Step-0 read turns per dispatch: median 2

CURRENT Step-0 cost .................................  46.0M
round-trip credit if the reads are removed ..........  19.6M
RELOCATED, naive placement ..........................  100.9M  => NET +35.2M (+3.07% of corpus)
RELOCATED, best case (identical block at byte 0 of
   all 8 defs, shared prefix cache across fan-out) ..   82.4M  => NET +16.8M (+1.46% of corpus)

residency term alone, unavoidable in ANY system-prompt placement: 75.9M
```

The mechanism: **the median dispatch loads only 12,716 of the 26,318 Step-0 tokens (48%), and 19% load under 5k.** Today's 46.0M is a partial bill. Any system-prompt placement makes it a full bill for 100% of dispatches from call 0 — and 75.9M of that is pure residency that caching cannot touch.

I checked the best case fairly, because pass 2's §7A hypothesis about shared prefixes is right about the preconditions: **84% of lens dispatches start within 5 minutes of a sibling** (median inter-dispatch gap 20s, 115 clusters of ≥4 covering 721 dispatches), and first-call `cache_read` is pinned at exactly **1,915** for both median and p75 — a fixed, tiny shared prefix that *does* cache. The infrastructure works; the shared segment is just 1,915 tokens long. So prefix sharing is achievable, and item #2 still loses.

Side effect: subagent median prefix **54,000 → 80,318 (+49%)** — numerically identical to the +48.7% seven-week drift that `report-corpus-autopsy.md:229` calls "the trend, not any single artifact, is the thing to arrest." Item #2 does a full quarter of that drift in one commit.

### The reliability premise: pass 2 said "no corpus evidence either way." There is evidence, and it cuts both ways

Two natural experiments, both involving content that is *already* in the agent system prompts:

- **Output-format mandate** — charter §3's "What I could not verify" section, restated in all 8 `review-*.md` defs. Emitted by **97%** of dispatches that never read the charter and **98%** of those that did. Passive presence ⇒ compliance, at parity.
- **Behavioral mandate** — `review-bdd.md:54`, "Run `python3 .claude/scripts/inspect_bdd_steps.py`," an imperative in the system prompt and nowhere else. Executed in **27%** of 101 bdd dispatches (26% charter-read, 29% not).

So: system-prompt presence reliably produces stated output shapes and unreliably produces stated actions. The charter is doctrine that must shape judgment — closer to the first case than the second, but neither settles it. Pass 2's "no evidence" claim is wrong; its "don't assume parity" conclusion is still the right posture, for a reason it did not have.

**The experiment that would settle it:** paired A/B on the same PR at the same head SHA — same lens, one dispatch with Step-0 as tool reads, one with it in the system prompt — graded on findings recovered against a known defect set, not on report length. Given the 8.5× dispatch cost variance, it needs pairing on PR+lens+round, and it needs ~30 pairs. Nobody has run it, and it is cheap compared to the +35M it would avoid.

**Cheaper alternative with the same reliability goal:** the §5 mandatory list sits at `review-charter.md:136` — line 136 of 151, behind ~37 KB of prose. Hoisting the 9-line list (~200 tok) to the top of each agent def costs 0.8% of what relocating the payload costs.

---

## 3. The 46.6% self-read figure — reproduces exactly, is not double-counted, and is unsafe to act on *as pooled*

I re-derived it independently. I get **157.6M / 46.8%**. The arithmetic is sound. The problem is that it is an average over two populations with opposite structure:

```
MAIN     154 threads | actual accumulated carry 201.4M
   own output 151.6M (74.2%) | tool results 42.8M (20.9%) | user 10.0M
   attribution closes at 101% of actual  ← trustworthy

SUBAGENT 859 threads | actual accumulated carry 267.7M
   own output   6.0M ( 4.5%) | tool results 126.4M (95.5%) | user 0.0M
   attribution closes at  49% of actual  ← half of subagent carry is UNEXPLAINED
```

- **Not double-counting.** `output_tokens` and `tool_result` bytes are disjoint, and 101% closure on main is the check: if stripped thinking blocks were *not* being re-sent, main closure would come in well under 100%.
- **Not an artifact of the over-predicting additive model.** That model over-predicted 99-384% because it ignored compaction; per-thread floor subtraction handles compacted threads correctly, and closure is 101%, not 200%.
- **But the pooled number hides that it is a main-thread-only phenomenon**: 74.2% of main carry (151.6M = 13.2% of corpus) and 4.5% of subagent carry (0.5% of corpus). Subagents are 56% of cost. Any fix aimed at subagent self-read recovers nothing.

While there: the single-regressor fit both reports rely on is **misspecified**. Adding the tool-result term:

```
MAIN     delta_ctx = 0.941·prev_output + 1.417·prev_toolresult + 1,032
SUBAGENT delta_ctx = -0.277·prev_output + 1.435·prev_toolresult + 1,415   [was -1.232 single-regressor]
```

Most of the bizarre −1.232 was omitted-variable bias. The real reason subagent output does not drive growth is that **mean subagent output is 53 tokens/turn against main's 2,641** — there is nothing to persist, not a failure to persist. Pass 2's inference happened to hold; its stated mechanism did not.

---

## 4. The correctness framing — the 43% is real, and it predicts nothing measurable

I reproduce the compliance defect at corpus scale (761 lens dispatches, not the 301 harness-anatomy identified — the 43% is on a 40% subsample; the corpus figure is 27%):

- 208 / 761 (27%) read **zero** of the 9 §5 files
- 214 / 761 (28%) never read the charter by any route
- **Not session-clustered**: 97 of 103 multi-dispatch sessions are mixed, so this is a per-dispatch property, not an orchestrator-prompt effect

Then I ran the test nobody ran — **do the low-compliance dispatches produce worse findings?**

| group | n | report size | severity findings (mean) | path:line cites (mean) | cost (median) |
|---|---|---|---|---|---|
| §5 files read: **0** | 208 | **12,339 B** | 5.0 | **18.0** | 790k |
| §5 files read: 1-8 | 237 | 10,742 B | 5.1 | 14.1 | 564k |
| §5 files read: **9** | 316 | 10,788 B | 4.9 | 15.1 | 637k |
| charter NOT read | 214 | 10,440 B | 4.8 | 12.6 | 533k |
| charter READ | 547 | 11,376 B | 5.1 | 16.8 | 698k |
| **neither** (n=53, 7%) | 53 | 10,114 B | 4.5 | 11.7 | 501k |

Dispatches that read **zero** mandated files produce **larger reports, the same finding count, and more path:line citations** than fully compliant ones — and cost 24% more. The mandated "What I could not verify" section appears in 97% of them. Only total non-compliance (7% of dispatches) shows any dip, and it is small.

**Conclusion: "43% of lens runs read zero mandated files" is a compliance fact with no measured correctness consequence in this corpus.** Pass 2 called it "a defect in the load-bearing harness, sitting in plain sight... and nobody named it" and used it to flip item #2's entire justification. The flip rests on an untested inference. The operative discipline is already delivered by the agent definitions, which are always present.

Honest limit: finding *count* is not finding *quality*, and I cannot grade correctness from transcripts. But the burden has moved. And the implication runs the other way from the plan: **208 dispatches skipped the 100,010 B payload entirely and got measurably no worse results.** That argues for shrinking Step-0, not for guaranteeing its delivery at +35M units.

---

## 5. What pass 2 got wrong that nobody caught — items #5 and #6 are rounding error, off by 12-30×

Pass 2 was told to attack pass 1's ranking. It re-ranked using **pass 1's per-invocation samples × assumed invocation counts** instead of measuring the corpus, and crowned `review_completeness.py --index` "worth more than the other four combined, several times over" at **3.3-9.4% of corpus**. I measured every GitHub-surface payload actually present (0 results carry a truncation marker, so these are the billed bytes):

| command class | calls | result bytes | ~tokens | carry+write | % corpus |
|---|---|---|---|---|---|
| `gh api` comments/reviews | 483 | 1,753,995 | 461,577 | 3.02M | 0.263% |
| `gh pr view` | 621 | 1,354,855 | 356,540 | 2.45M | 0.213% |
| `gh pr diff` | 128 | 469,479 | 123,547 | 0.64M | 0.056% |
| **`gh run view` (CI logs)** | **59** | 239,932 | 63,140 | **0.62M** | **0.054%** |
| **`review_completeness.py`** | **138** | 162,662 | 42,805 | **0.25M** | **0.022%** |
| **all five combined** | | | | **6.98M** | **0.608%** |

- **Plan #5 (`--index`)**: ceiling is 0.022% (its own output) plus whatever share of the 0.263% hand-rolled re-pulls it displaces. **Absolute ceiling 0.285%.** Pass 2 said 3.3-9.4%. Over by 12-33×.
- **Plan #6 (`ci_failure.py`)**: ceiling **0.054%**, of which anchor-windowing captures ~0.053%. Pass 2 said 0.71%. Over by 13×.

The mechanism of the error is visible: `gh run view` results in this corpus average **4,067 bytes**; FACTS.md's sampled job was 90,229 B — **22× the corpus mean**, and the pricing assumed ~100 invocations against an actual 59. `review_completeness.py` ran 138 times, not "306-533."

So pass 2 preserved pass 1's cardinal error — generalizing from a sampled PR — while loudly correcting pass 1 for it elsewhere. That is where the attack-the-predecessor bias took it too far.

---

## 6. The unexamined premise — I tested it. It does not hold.

79 PRs, 120 lens-running sessions:

```
sessions per PR: {1: 53, 2: 18, 3: 5, 5: 2, 6: 1}   mean 1.52, median 1
round 1 (first session per PR) : 710.6M (66%)
rounds 2+ (re-reviews) ........: 370.7M (34%)
```

**67% of PRs got exactly one review session.** So there is no epidemic of re-review. And the re-reviews that do happen are not churn:

| round | dispatches | BLOCKER+MAJOR (mean) | zero-finding rate | share of lens cost |
|---|---|---|---|---|
| r1 | 435 | 1.54 | 1% | 52% |
| r2 | 168 | 1.22 | 6% | 23% |
| r3 | 64 | 1.22 | 5% | 11% |
| r4+ | 87 | 1.29 | 7% | 15% |

The decisive test — **is a re-review re-deriving what an earlier round already found?** Over 272 re-review lens reports comparable to an earlier round of the same PR+lens, the fraction of `path:line` citations already cited in an earlier round is **median 0%, mean 7%, p90 20%. 51% have zero overlap. Exactly 1 of 272 exceeds 50%.**

**"Reviews re-run on unchanged code" and "too many review rounds" are falsified.** Rounds 2+ cost 48% of lens-dispatch spend and return 79-84% of round-1's per-dispatch blocker yield on ~93% novel ground. They earn it.

The *size* version of the premise is a different story and is real: **PR #1417 alone is 103.1M units = 9.0% of the entire corpus** across 3 sessions and 72 lens dispatches (9 full panels). PR #1547 ran 6 rounds escalating monotonically 5.0 → 8.7 → 5.1 → 6.8 → 12.8 → **26.4M**. Eight PRs carry 36% of all PR-attributed cost. A **per-PR cumulative cost budget** is a live lever. A round-count cap is not.

---

## 7. Item #1 (detector false-greens) — simply correct, and I upgraded it from synthetic to shipped

`report-detector-map.md:207` concedes: "The false-greens are proved on synthetic inputs... I did not confirm any shipped artifact actually passed through one." I checked. I ran `disposition_ledger.audit()` over all 81 real artifacts in `/Users/quantum/Documents/ComputedChaos/salesagent/.claude/reports/`:

- 50 artifacts contain ≥1 severity-tagged finding; **15 get a CLEAN verdict**
- Of those 15, **5 contain finding blocks with no disposition token anywhere in the document referencing them — 9 blocks out of 259, including one BLOCKER**

```
full-review-pr1698-rereview-20260731.md   2/25 blocks (ids D1, F1)
full-review-pr1676-20260730_1330.md       3/30
full-review-pr1547-rereview-20260716.md   2/7
full-review-pr1682-rereview-20260729.md   1/15  <- [BLOCKER] "the request credential reaches
                                                    the buyer wire and three persisted sinks"
full-review-pr1575-rereview-20260720.md   1/12
```

The defect at `disposition_ledger.py:189` (`deficit = max(0, n_findings - n_dispositions)`, a document-wide count) is not theoretical. **A BLOCKER has shipped through the gate undisposed.** Fix as specified — split on `FINDING_TAG:74` boundaries. Caveat: my per-block splitter can miss a disposition phrased outside `DISPOSITION_TOKENS`; treat 9 as an upper bound and the two ID-matched blocks plus the BLOCKER as the confident core. That is still enough.

**Item #4** (delete charter §4b/§4c) reprices to **~0.59%** (2,936 tok × [1.25 + 30×0.10] × 547 charter-loading dispatches) — larger than #5 and #6 combined. Pass 2's scoping correction is load-bearing and correct: §4c.2/.3/.4/.5 are agent-facing (§4c.3 at `review-charter.md:129` is written in the second person to the raising agent). Delete **§4b + §4c.1 + §4c.6 only.**

---

# Verdict

**STOP**

- **#2 — relocate Step-0 into the 8 agent system prompts.** Net **+16.8M to +35.2M units (+1.46% to +3.07% of corpus)** under every placement including the best-cached one, because 75.9M of residency is unavoidable and today's bill is only 46.0M (the median dispatch loads 48% of the payload). It adds +49% to the subagent prefix — the exact drift the corpus autopsy names as the thing to arrest. And it buys compliance that this corpus shows does not change output. If the reliability case is to be made, make it with the paired A/B above, not by assertion.
- **#5 — `review_completeness.py --index`.** Absolute ceiling **0.285% of corpus** (0.022% for the script's own output, 0.263% for every `gh api` comment/review pull in 159 sessions combined). Pass 2's own risk analysis of it is correct: it discards 78-88% of reviewer prose and sits on the readiness gate. All risk, no reward. Its only defensible form is the *cheap* half — add `--since` as an `argparse` requirement (charter `:126` says it is "not optional"; it is omitted in 41% of runs) — which costs nothing and fixes a real gate hole.

**SAFE**

- **#1 — the 4 detector false-greens.** Correct, and now confirmed on shipped artifacts with a BLOCKER through the gate. Ship first; it is the only item that touches correctness rather than cost.
- **#4 — delete §4b + §4c.1/.6 from the charter.** ~0.59%, pure deletion, no capability lost. Do not delete §4c wholesale.
- **#3 — lower `autoCompactWindow`, but to 400-500k, not 300k.** At 400k: 63 events, net **+3.0% to +5.9%** after charging both the summarization call and the measured 47-66k cache-write burst per event. At 300k it reaches +4.5-8.6% but fires mid-panel in 15 review sessions, and the summarizer demonstrably drops the finding ledger (0 severity labels in 3 of 5 real events). If you want 300k, first gate compaction so it cannot fire between a round's first and last lens dispatch.
- **#6 — `ci_failure.py`.** Harmless and correct, but it is worth **0.054%**. It is a chore, not a plan item. Do not spend a review round on it.

**The single most dangerous assumption still standing**

> **That the 100,010 B Step-0 payload is load-bearing.**

Every item in the plan treats it as a fixed input — to be delivered more cheaply (#4), more reliably (#2), or worked around. Nobody has tested deleting it. The corpus already contains the natural experiment: **208 lens dispatches loaded none of it and produced larger reports, more `path:line` citations, and the same number of severity-tagged findings than the 316 that loaded all of it.** It costs 46.0M units today and would cost 100.9M under item #2. It is the largest single expense in the review path whose value has never been measured in either direction — and the one piece of evidence that exists points at "less than assumed."

Runner-up, because it is the item most likely to ship next: **that summarization is content-preserving enough to be a cost lever.** For general work it may be. For a review it is not — measured, on real events, the ledger does not survive.

---

**What I could not measure.** The summarization call's true billing (absent from the transcript; I bounded it by observing the pre-boundary prefix is cached, so cache-read pricing is the right assumption, not the floor). Finding *quality* as opposed to count, citation density, and report length — my §4 conclusion rests on those proxies. Whether the 9 undisposed finding blocks were dispositioned in prose outside `DISPOSITION_TOKENS`. Whether a 400k cap also lands mid-panel (I measured that only at 300k). My compaction simulation returns −0.8% at cap=985k where it should return ~0, which bounds all its figures at roughly ±1%. Scripts are at `/tmp/sim.py`, `/tmp/x3.py`, `/tmp/x5.py`, `/tmp/x6.py`, `/tmp/x7.py`, `/tmp/out.py`, `/tmp/out2.py`, `/tmp/out3.py`, `/tmp/price3.py`, `/tmp/best2.py`, `/tmp/carry.py`, `/tmp/reg2.py`, `/tmp/pr.py`, `/tmp/round.py`, `/tmp/rep.py`, `/tmp/tools2.py`, `/tmp/runway.py`, `/tmp/fan.py`.