I have everything measured. Final report follows.

---

# Subagent output: what generates 178.7M cost units

## 0. Validation — reproduced, with one correction

I re-derived the regression from raw transcripts before using it.

| coefficient | report | my refit |
|---|---|---|
| `out_prev` | 0.9915 | **0.9927** |
| `tool_result_chars` | 0.4053 | **0.4087** |
| `n_tool_results` | 63.70 | **65.18** |
| R² | 0.9925 | **0.9960** |

The filter that reproduces their sample exactly is *"within-turn transition with **no `attachment` or `system` record** in the gap"*: **n = 6,211** (theirs: 6,211) and actual output on that set **15,375,126** (theirs: 15,375,126). Confirmed.

**Correction: the −0.84% back-test is in-sample.** On that filtered set I get +0.11%. Applied to *all* 8,519 main-thread within-turn transitions it is **+11.80%**. The excess is not noise — it is `attachment`/`system` injections, which add context the inversion misattributes to output. On the 2,308 transitions containing one, residual/actual is **+41.9%**; on the 6,211 without, **+0.11%**.

This does **not** invalidate the subagent figure: subagents have ~33 attachment records across the whole corpus versus 1,597 in main. The bias mechanism is absent where the method is applied. I tested and rejected my own first hypothesis (cache re-warm): bias is +11.87% even in the no-re-warm subset.

**A second correction, this one material to your headline.** The report extrapolated the 859 unrecoverable final-call outputs at the *per-call mean* (1,118 tok → 0.96M). But the final call is the one that emits the report; its **visible content alone averages 4,443 tok — 4.0x that mean**. Floor total is **38.65M**, not 35.73M; if final calls carry the same 65% reasoning share as every other call, **45.7M**. So subagent output is **193–229M cost units, not 178.7M** — **14.7–17.4% of corpus cost, not 13%**.

**Also correcting FACTS.md line 28.** "Reasoning ≈ 75-84% of main-thread output" comes from the 3.8 chars/token constant. I calibrated it empirically on 820 no-thinking main calls: **text is 2.66 chars/token** (stable 2.65–2.76 across every size bin, intercept −5, R² = 0.9996) and tool-call JSON 2.61. At 3.8 you get 74.5%; at the measured rate, **main-thread reasoning is 63.5%** — very close to the subagent figure, not 20 points above it.

---

## 1. The split

Reconstructed subagent output, 31,144 calls:

| | tokens | share |
|---|---|---|
| **reasoning (invisible)** | 22,640,623 | **65.0%** |
| tool-call JSON | 8,951,602 | 25.7% |
| visible prose | 3,241,086 | 9.3% |

Per lens the eight review lenses are **strikingly uniform** — reasoning 64.7–69.3%, prose 7.9–9.8%, JSON 22.7–26.9%. `review-bdd` is the outlier at 69.3% reasoning. Only `general-purpose` differs structurally (44.6% reasoning, 21.2% prose).

The 8-lens panel is 759 dispatches, **36.66M tokens**, 95.5% of all subagent output. Full budget:

| | tokens | share | per dispatch |
|---|---|---|---|
| reasoning | 21,931,924 | **59.8%** | 28,896 |
| tool-call JSON | 8,407,409 | 22.9% | 11,077 |
| **final report (delivered)** | 3,403,857 | **9.3%** | 4,485 |
| interstitial prose (discarded) | 2,916,021 | 8.0% | 3,842 |

---

## 2. Where in a dispatch — mildly back-loaded, no report spike

750 review dispatches with ≥10 calls, by decile:

| decile | tok/call | % of output | reason% | json% |
|---|---|---|---|---|
| 1st | 424 | 4.1% | 49.0% | 44.9% |
| 2nd | 841 | 7.2% | 63.4% | 29.1% |
| 5th | 1,196 | 10.0% | 65.0% | 25.6% |
| 9th | 1,435 | 12.6% | 67.4% | 23.1% |
| 10th | 1,691 | 12.9% | 73.1% | 19.0% |

**Neither profile you posited.** Output ramps 4x from first decile to last, but is flat from decile 3 onward (9.5% → 12.9%). The first decile is *cheap* — that is the Step-0 charter/memory reads, mechanical `Read` calls with little to reason about. The last decile shifts toward reasoning (73.1%) and away from tool JSON (19.0%), which is synthesis, but it is not a prose spike (prose stays at 7.9%).

Phase view: **Step-0 reads are 0.6% of output**; investigation is 90.1%; the report call 9.3%. The charter-read problem in FACTS.md is an *input* problem — it costs almost nothing in output.

---

## 3. The report is 9.3%

Mean panel report **11,913 B = 4,485 tok**, against 48,329 tok of dispatch output. **11 tokens generated per token delivered to the orchestrator; 90.7% is generated and discarded.**

Incidental finding on delivery mechanics: the `Task` tool_result in the parent transcript is **not** the report — it is a 1,082 B async launch ack (`"Async agent launched successfully… agentId: …"`). Only 9.8% of dispatches matched on that join. The report actually arrives later as a **`queue-operation`** completion notification (89 of 120 probed; 20 as `user` records; 10 not located). It is delivered in full — but anyone joining subagents to parents via `toolUseId` → `tool_result` will conclude the orchestrator receives ~900 bytes. It doesn't.

---

## 4. What is wasted — and three things that are not

**The dominant waste is structural, not stylistic: reasoning is flat per round-trip, independent of payload.**

| evidence size the call reasons about | calls | reasoning | tok/call | **tok per KB** |
|---|---|---|---|---|
| 0–500 B | 20.9% | 15.8% | 591 | **2,393.7** |
| 500 B–2 KB | 28.6% | 29.0% | 794 | 691.6 |
| 2–8 KB | 35.8% | 40.5% | 884 | 215.5 |
| 8–30 KB | 13.2% | 13.5% | 795 | 53.7 |
| >30 KB | 1.5% | 1.3% | 679 | 15.0 |

Reasoning per call varies by 1.5x while evidence varies by 100x — a **160x swing in tokens per KB**. **49.5% of calls follow a result under 2 KB and consume 44.8% of all reasoning.** 74.5% of panel reasoning follows a `Bash` result averaging 3,170 B. Meanwhile **71.0% of calls issue exactly one tool** (mean 1.49), and **51.5% are back-to-back single calls using the same tool.**

That is the re-planning cost you asked about, and it is the largest single addressable block: **13.76M tokens (37.5% of panel output) is reasoning on single-tool round-trips.**

**Narration** is real but second-order. 25.7% of interstitial blocks open with a narration cue; those opening lines alone are ~305k tok extrapolated to the panel. Real examples with cost:

> `'Now the remaining mandatory charter Step-0 memory reads.'` — 56 B ≈ **21 tok**, review-test-integrity call 8/47
> `"I'll start with the mandatory Step-0 reads, then set up my tree."` — 64 B ≈ **24 tok**, review-security call 1/104
> `'Step-0 reads done. Now asserting tree state before any run.'` — 59 B ≈ **22 tok**, review-architecture-guards call 4/82

Charter/Step-0 restatement is 10.8% of interstitial bytes (24,719 tok in a 60-dispatch sample ≈ **313k tok** panel-wide). All interstitial prose — **2.92M tok, 8.0% of panel output** — is generated, billed at 5x, re-read at 0.10x for the rest of the dispatch, and never seen by the orchestrator.

**Three suspected wastes I tested and did not find:**

1. **Report ≠ restatement of working notes.** 8-word shingle overlap between the final report and all interstitial text: **median 0.4%, mean 0.7%** (n=115). The report is freshly composed. The double-write hypothesis is false — total duplicated content is ~22k tok corpus-wide.
2. **Preamble before the report is negligible.** Median 216 B, **2.8% of final-call text, ~97k tok** panel-wide. And most of it is substantive verification ("*All mutations restored clean. Report follows.*").
3. **Repeated tool calls barely exist.** Exact-duplicate `Bash` commands within a dispatch: **45 of 28,753 (0.2%)**.

The long interstitial blocks (>800 B, 33.8% of interstitial bytes) are genuine finding drafts with `[observed]` tags and `path:line` citations — analytic work, not narration.

---

## 5. Verbosity vs quality — it buys NITs

721 of 759 panel dispatches carry a parseable `Summary: N BLOCKER / M SHOULD-FIX / K NIT` line. Mean 0.12 BLOCKER, 1.61 SHOULD-FIX, 2.21 NIT; only 2.6% report zero findings.

The confound is real and strong — evidence bytes read correlates +0.417 with output and +0.418 with findings. Partial correlations controlling for it:

| output vs | raw r | **partial r \| evidence** |
|---|---|---|
| NITs | +0.294 | **+0.189** |
| findings incl. NIT | +0.308 | +0.162 |
| BLOCKER + SHOULD-FIX | +0.227 | **+0.083** |
| path:line citations | +0.224 | **+0.007** |
| BLOCKERs | −0.037 | **−0.088** |

Stratified by difficulty tercile, splitting each at its output median:

| difficulty | extra output | extra findings | **tok per marginal actionable finding** |
|---|---|---|---|
| low | +26,739 | +0.47 | **356,521** |
| mid | +28,742 | +0.85 | 90,765 |
| high | +32,844 | +1.48 | 51,093 |

Panel average is 28,271 tok per actionable finding. **On easy PRs the marginal token costs 12.6x the average and buys almost nothing actionable** — verbosity there is close to pure cost. On hard PRs it still pays, at roughly 1.8x average. Extra output does not buy BLOCKERs (negative) and does not buy evidence anchoring (zero).

No lens is a safe downgrade target: tok-per-actionable spans only 24,426 (`review-code-patterns`) to 38,646 (`review-bdd`), and reasoning share is uniform 64.7–69.3%. There is no mechanical lens hiding in this panel.

---

## 6. What would actually reduce it

Ranked by saving-per-unit-of-risk. Panel output is 36.66M tok = 183M cost units.

**1. Batch tool calls — 2.5% to 14.1%, no capability loss.** 14,735 back-to-back single-tool calls could merge pairwise, removing ~7,367 round-trips. Conservative bound (removed calls are the cheapest): **0.93M tok, 2.5%**. Central (removed calls are average): **5.19M tok, 14.1%**. I cannot narrow this further — reasoning per single-tool call is bimodal (44% under 100 tok, p90 = 1,906), and I cannot prove the reasoning wouldn't simply migrate to the merged call. **Zero evidence is lost** — the same bytes are read either way. This is the only lever that cuts cost without touching what the agent looks at.

**2. Effort/verbosity cap on low-difficulty dispatches only — up to ~8%, low risk.** Gate on evidence-bytes read (measurable at runtime). The low-difficulty tercile's high-output half spends +26,739 tok/dispatch for +0.07 actionable findings. Capping that half to its cohort median saves ~1.6M tok panel-wide (~4.4%), and the measured yield loss is 0.07 actionable findings per dispatch. **This is a genuine trade, just a very favourable one** — but it is still a trade, so it belongs in front of Chris, not applied silently.

**3. "Do not narrate" instruction — ~1–3%, near-zero risk.** Narration openers ~305k tok, charter restatement ~313k tok. Even eliminating all interstitial prose caps out at 2.92M (8.0%), and ~64% of it is substantive finding drafts you would not want to suppress. Realistic: **0.6–1.1M tok, 1.7–3.0%**. Cheap to try, small payoff. Note the instruction itself costs context on every dispatch.

**4. Shorter mandated report format — ~4.6%, and I recommend against it.** Halving the report saves 1.7M tok (4.6%). But the report is the **only 9.3% the orchestrator ever sees**, and report length is the weakest-correlated variable in the whole dataset (r = +0.187 raw with output). You would be cutting the deliverable to save less than batching gives you free. **This is a findings-for-tokens trade — the cardinal sin, correctly labelled.**

**5. Structured output schema instead of prose — negligible saving, real risk.** It only touches the 9.3%, and reports already carry a machine-readable `Summary:` line plus `[observed]` tags and `path:line` citations. Converting the prose body to JSON would raise token density (JSON tokenizes at 2.61 chars/token vs 2.66 for prose — no gain) while removing the reasoning-trace the orchestrator uses to judge findings. **Not worth it.**

**6. Cheaper models for mechanical lenses — cannot be assessed from this data.** All 23 haiku dispatches are `Explore`, none are review lenses, and the reconstruction fails on them (estimated output is 2.1x *below* measured visible content, so haiku transitions violate the model's assumptions). I have no evidence either way and will not guess.

---

## What I could not measure

- **Final-call output is unrecoverable in principle** — it never re-enters any context. I measured only its visible content (4,443 tok/dispatch); final-call *reasoning* is unmeasured, which is the entire 38.6M–45.7M uncertainty band.
- **Per-call reconstruction is noisy.** 37.4% of calls yield an estimate below their own measured visible content. Aggregates are validated; I did not use per-call values except in bucketed means where errors average out.
- **The 2.66 chars/token rate is calibrated on main-thread output and assumed to transfer.** It cannot be verified on subagents, because the field it would be checked against is the stub.
- **"Quality" here is finding counts and citation density, not validated defect discovery.** I did not check whether any finding was correct, or whether it survived to the merged PR. A dispatch that reports 5 NITs scores above one that reports 1 true BLOCKER.
- **The batching saving is a bound, not a point estimate** — the 2.5%/14.1% spread is irreducible without an experiment.

Scripts are at `/private/tmp/claude-501/-Users-quantum-Documents-GitHub-agenticads-sim-plan/e2367c8b-0c8b-43ae-a5d4-98ce3fbcecea/scratchpad/sa/` (`lib.py` loader, `repro*.py` validation, `q1b/q2/q3/q4*/q5*/q6*.py` per question). No transcript was read whole; everything streams line-by-line. No files in the repo were touched.