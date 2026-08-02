Measurement complete. Here is the settlement.

---

# The calibration is settled: 2.67 chars/token for text, 2.53 for tool JSON, plus a framing term

Scripts: `/private/tmp/claude-501/-Users-quantum-Documents-GitHub-agenticads-sim-plan/e2367c8b-0c8b-43ae-a5d4-98ce3fbcecea/scratchpad/cal/` (`build.py` → `core.py` → `ser.py` → `leak.py` → `repro.py` → `sweep.py` → `fit.py` → `robust.py` → `totals.py` → `subfinal.py`). Read-only; no repo file touched.

## 1. The correct method and value

**No chars/token scalar is the right answer.** Billed output is content-proportional *plus* a fixed framing cost per tool call, so any single ratio is a function of the call-size mix you happened to sample. The correct object is an estimator:

```
vis_tok = 0.37458·text_chars + 0.39539·tool_json_chars + 69.74·n_tool_use + 17.30·n_calls
```

| term | value | 95% CI (bootstrap, 600×) | jackknife (leave-one-session-out, 94 sessions) |
|---|---|---|---|
| visible text | **2.67 chars/token** | 2.63 – 2.71 | 2.654 – 2.679 |
| tool-call JSON | **2.53 chars/token** | 2.47 – 2.59 | 2.497 – 2.547 |
| per `tool_use` block | 69.7 tok | — | — |
| per call | 17.3 tok | — | — |

**Exact filter:** main-thread `assistant` records → drop repeat `uuid` (session-resume replay) → group by `requestId`, unioning content blocks → drop `model == "<synthetic>"` → keep calls with **no `thinking` block present in any record** → `output_tokens > 0`. **n = 820** (69 text-only, 654 tool-only, 97 mixed). R² = 0.99644; in-sample aggregate bias 0.000%; **5-fold CV aggregate bias +0.13%** (folds −0.81/+1.57/+0.66/+0.65/−1.44%).

Robustness: the text rate is 2.665–2.702 dropping the 1/2/3/6/10/20 largest calls, 2.687 on calls under 2,000 chars and 2.670 on calls over. It is not resting on the six big review comments. By model: 2.585 (opus-4-8), 2.683 (opus-5), 2.575 (fable-5) — one tokenizer.

**Independent cross-check from the other side of the ledger.** Tool results are 100% visible in the transcript and their cost is exact billing, so nothing can hide in them. Regressing context growth on tool-result content over 3,289 pure-tool-result transitions gives **2.48 chars/token** (+80.4 tok/result). An input-side measurement that structurally cannot be contaminated by reasoning lands within 8% of the output-side rate. **3.80 is not close to either.**

Two things I checked and could not use: no tokenizer exists offline (`tiktoken`, `transformers`, `tokenizers`, `sentencepiece`, `anthropic` all absent from all four Python installs; no vocab/merges file anywhere under `~/.claude`, `~/.nvm`, or the frameworks; no node tokenizer package). And calibrating prose against subagent dispatch-prompt length fails — within-group R² is 0.002–0.29 because the static floor is not constant within an agentType (`cal/prose.py`). Both reported rather than fudged.

## 2. Why the three figures disagree — one cause, not three

The relationship is `tokens = content + framing`, so **chars/token rises monotonically with call size**: 1.40 in the smallest output quintile, 1.58, 1.75, 2.06, 2.47 in the largest. Every disputed number is a different weighting of that curve.

| figure | what it actually is | reproduces? |
|---|---|---|
| **1.92** (orchestrator) | **mean of per-call ratios** over filter-A calls with ≥208 visible chars | **yes — 1.918 at exactly n = 719** |
| **2.66 / 2.61** (report-subout) | OLS *slope*, text and JSON separated | yes — my slopes are 2.67 / 2.53 |
| **2.28** | pooled Σchars/Σtokens over the same 820 | yes |
| **3.80** (FACTS.md) | assumed; no measurement behind it | n/a |

**1.92 is a weighting artifact, not a measurement.** A mean of per-call ratios equal-weights a 200-char tool call with a 40,000-char review comment. Because the ratio is size-dependent, that mean converges on the *median-sized call's* ratio, which is not the corpus rate and not the marginal rate — it answers a question nobody asked. Reproduced exactly: filter A + `vis_chars ≥ 208` + mean-of-ratios → n=719, 1.918.

**2.66 is right as a slope but incomplete as an estimator** — dropping the framing terms under-counts main-thread visible output by 986,469 tokens and subagent visible output by 3,785,426 tokens (10.6% of subagent output).

**3.80 is simply wrong for this corpus.** The content is technical markdown: 7.2–7.5 chars/word (English is ~5.5) and 2.65–2.84 tokens/word (English is ~1.3), dense with `path:line` citations, commit SHAs, and identifiers like `_task_push_configs`.

Two checks that came back clean, so I am not attributing any of the gap to them:
- **No thinking leaked into the sample.** Zero of 820 calls violate the hard character ceiling (`output_tokens > total visible characters` is physically impossible; excess = 0 tokens, 0.00%). The competing filter *"thinking text is empty"* — which sweeps in the 4,696 emptied-thinking calls — collapses to 0.799 chars/token, so it is trivially distinguishable and was not used by either party.
- **The estimator is not over-fitted to its sample.** Applied to the 8,936 thinking calls it predicts more visible output than was billed on only 53 calls (0.6%), total overshoot 7,997 tokens. Refitting on text-bearing calls only, tool-bearing only, `vis_chars ≥ 500`, opus-5 only, or opus-4-8 only moves the main reasoning share only between 61.7% and 63.2%.

## 3. Serialisation explains essentially nothing

`cal/ser.py`, tool-only calls, n=654. The slope is invariant to four significant figures:

| serialisation | total chars | slope (tok/char) | chars/token | naive pooled ratio |
|---|---|---|---|---|
| compact `separators=(',',':')` | 851,852 | 0.39029 | 2.56 | 2.147 |
| `indent=2` | 860,420 | 0.39017 | 2.56 | 2.168 |
| `indent=4` | 864,354 | 0.39012 | 2.56 | 2.178 |
| XML `<parameter>` form | 887,273 | 0.39468 | 2.53 | 2.236 |
| full block incl. `id` + `name` | 908,973 | 0.39028 | 2.56 | 2.290 |

R² spread across all five: 0.00051. **Serialisation choice moves the answer by 0% under a regression and at most 6.7% under a naive pooled ratio.** It is not the driver. It is, however, physically visible in the framing term: `tool_use` ids are 30 chars of `toolu_` + base62 (9.5 pre-tokens each), and adding `id`+`name` to the string moves the per-tool coefficient from +9.76 to −23.24 — the id absorbs it exactly, which is what should happen. The 27-token floor observed five times identically on `TaskList` with `input: {}` is that framing measured directly.

## 4. What the settled value does to the conclusions

### Main thread — gold standard, no reconstruction anywhere

9,756 calls, **25,757,282 billed output tokens** (measured, not estimated). 6,937,152 chars of visible text; 15,249,147 chars of tool JSON; 11,725 tool_use blocks.

| | tokens | share |
|---|---|---|
| **reasoning (invisible)** | 16,142,999 | **62.7%** |
| tool-call JSON | 6,029,304 | 23.4% |
| visible prose / reports | 2,598,511 | 10.1% |
| tool-call framing (id, name, wrapper) | 986,469 | 3.8% |
| **all visible** | **9,614,283** | **37.3%** |

**Bootstrap 95% CI on the reasoning share: 62.1% – 63.3%.** Composition refits span 61.7–63.2%.

Against the alternatives: 3.80 → 77.3%; 2.66/2.61 without framing → 67.2%; 1.92 → 55.1%.

### Subagents — softer, because the output total is itself reconstructed

Independently recounted (exact match to the cached extract): 32,032 calls, 20,097,877 text chars, 18,260,268 JSON chars, 46,334 tool_use blocks → **18,533,526 visible tokens**.

Splitting by position, which turns out to matter more than the calibration:

| | n | visible tokens | per call |
|---|---|---|---|
| non-final calls | 31,173 | 14,713,217 | 472 |
| **final (report) calls** | 859 | **3,820,309** | **4,447** |

On non-final calls, against report-blind's 34,772,351 reconstruction: **reasoning 20,059,134 = 57.7%**, visible 42.3%.

The 859 final calls never re-enter any context and are unrecoverable in principle, so the subagent total is a range:

| closure for final calls | subagent total | visible | reasoning |
|---|---|---|---|
| floor (visible content only, zero reasoning) | 38,592,660 | 48.0% | **52.0%** |
| same reasoning share as non-final calls | 43,801,045 | 42.3% | **57.7%** |
| report-blind's per-call-mean extrapolation | 35,732,713 | 51.9% | 48.1% |

**The third closure is refuted by its own data** — it puts final-call output at 960,362 tokens when those calls demonstrably contain 3,820,309 tokens of visible content. report-subout was right to reject it; the floor is 38.59M, confirming their 38.65M independently.

**Where report-subout's 65% came from.** Two mechanisms, both in `sa/q1.py:16-18`, and neither is the chars/token constant:
1. `if vis>e: s=e/vis; txt*=s; tj*=s; vis=e` then `rea=max(0,e-vis)` — visible is capped down when per-call reconstruction noise runs low, but never capped up when it runs high; the excess lands in reasoning either way. A ratchet, on a per-call estimate they themselves reported is below measured visible content on 37.4% of calls.
2. Their §1 total excludes the 859 final calls, which is where 3.82M of the 18.53M visible tokens live — the highest-visible calls in the corpus, removed from the numerator.

Their §1 table is also internally inconsistent with their own §2: 3.24M "visible prose" for all subagents, against 6.32M (2.92M interstitial + 3.40M report) for the 8-lens panel alone, which they state is 95.5% of subagent output.

### What does not move

**Total output cost units are unchanged by this calibration.** Output tokens are measured directly on main and reconstructed from context deltas on subagents; chars/token never enters either. The corpus output figure moves only because of the final-call closure: **321.7M – 347.8M cost units** (main 128.8M fixed, subagent 193.0M – 219.0M), versus 307.4M under the refuted closure.

report-subout's per-dispatch report size also survives: 11,913 B / 2.67 = 4,462 tok against their 4,485. The "report is 9.3% of dispatch output" finding stands.

## 5. Decision impact, stated plainly

**Reasoning is still the single largest component of output, but it is no longer "dominant and untouchable" — and on subagents it is now roughly half, not two-thirds.**

- **Main thread: reasoning 62.7% (CI 62.1–63.3%). Output reduction targets 37.3% of main output** = 9.61M tokens = **48.1M cost units.**
- **Subagents: reasoning 52.0–57.7%. Output reduction targets 42.3–48.0%** = 18.53M tokens = **92.7M cost units.**
- **Corpus: reasoning 56.5–60.4%. Output reduction targets 39.6–43.5%** = 28.15M tokens = **140.7M cost units**, which is **10.2% (TTL-corrected) to 10.7% (prescribed) of total corpus cost.**

The largest single directional change is on subagents. Under the old figures visible output was 35% of subagent output and easy to dismiss; it is now 42–48%, and **visible output is the larger half of subagent output under the floor closure**. Concretely, the 3.82M tokens in the 859 final reports and the 7.22M tokens of tool-call JSON are legitimate targets that the 65% figure was hiding.

What this does *not* change: FACTS.md's standing constraint still binds. Visible output being addressable is not an argument for shortening the reports — report-subout's §6.4 already showed report length is the weakest-correlated variable in the dataset, and that conclusion used the correct 2.66 rate, so it is unaffected. The batching lever (§6.1) is where the newly-visible headroom actually sits, since it removes round-trips and therefore removes framing *and* per-call reasoning together.

## 6. What would pin it tighter, and what I could not measure

- **The band is already tight where it matters.** Main-thread reasoning is 62.7% ± 0.6pp. That number needs no further work — it uses true billed output with no reconstruction step.
- **The subagent band (52.0–57.7%) is not a calibration problem and will not close with a better tokenizer.** It is the 859 final-call outputs, which never re-enter any context and are unrecoverable in principle. Only a live experiment — running one dispatch with the response captured — would close it.
- **What a real tokenizer would buy:** it would replace the ±0.04 chars/token bootstrap interval with an exact figure and would confirm or refute the 69.7 tok/block framing term directly. It would move the main reasoning share by well under a percentage point. Not worth acquiring for this decision.
- **Not measurable from this corpus:** the true unsummarized thinking text (Claude 4+/5 return a summarized thinking block while billing the full trace, which is why `thinking` chars can never be used as a reasoning proxy — report-blind's §6 note 2 is correct); and whether the ~470 tok/call non-final subagent visible estimate holds for haiku dispatches, since the reconstruction violates its own assumptions on those 23 files.

**One correction to carry back to FACTS.md line 28:** `3.8` should be replaced by the estimator above, and "Reasoning ≈ 75-84% of main-thread output" should read **"≈ 63% of main-thread output, ≈ 52–58% of subagent output."**