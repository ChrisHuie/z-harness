# Blind replication: cost model for the `salesagent` Claude Code corpus

## Corpus layout (derived, not assumed)

`/Users/quantum/.claude/projects/-Users-quantum-Documents-ComputedChaos-salesagent/`

| Path pattern | Count | Bytes |
|---|---|---|
| `./*.jsonl` — main-thread sessions | 159 (157 with API calls) | 239.4 MB |
| `./<parent-session-uuid>/subagents/agent-*.jsonl` | 859 | 444.5 MB |
| `./<parent-session-uuid>/subagents/agent-*.meta.json` | 859 | — |
| `./<parent-session-uuid>/tool-results/*.txt` | 97 (in 54 sessions) | 33.5 MB |
| `./memory/*.md`, `./sessions-index.json` | 169 + 1 | not transcripts |

Subagent transcripts nest one level under the **parent session's UUID directory**, so subagent cost is attributable to a parent. 130 sessions spawned subagents. `.meta.json` carries `agentType`, `description`, `spawnDepth`, `toolUseId`.

---

## 1. How many real API calls

**Yes, the format writes multiple records per API call — two independent mechanisms.**

**(a) Content-block splitting.** One API response is written as one `assistant` record *per content block* (`thinking`, `text`, `tool_use`), and **every one of those records carries a byte-identical full copy of the `usage` object**. Verified on `msg_01ETYscsje6ydfdhkFLtxmPD`: 3 records, 3 identical usage objects, one `requestId`. Naively summing `usage` across records inflates every token total by ~2.8x.

**(b) Whole-record replay.** On session resume, prior records are re-appended verbatim — same `uuid`, `parentUuid`, `timestamp`, `requestId`. 291 such records in the main thread, 0 in subagents.

**De-duplication:** drop records whose `uuid` was already seen (kills (b)), then key on `requestId` (kills (a); `message.id` gives the same partition). Then drop `model == "<synthetic>"` records — 71 of them, all with all-zero usage; these are harness-generated, not API calls.

| | assistant records w/ `usage` | synthetic | **real API calls** | records/call |
|---|---|---|---|---|
| Main | 28,855 | 43 | **9,756** | 2.95 |
| Subagent | 88,614 | 28 | **32,032** | 2.77 |
| **Total** | **117,469** | 71 | **41,788** | **2.81** |

`requestId` sets for main files and subagent files are **disjoint** (0 overlap), so the two scopes partition cleanly with no double counting.

---

## 2. Total tokens by category

| | fresh input | cache creation | cache read | output |
|---|---|---|---|---|
| **Main** (9,756 calls) | 2,258,890 | 85,606,148 | 2,687,416,407 | 25,757,282 |
| **Subagent** (32,032 calls) | 2,378,457 | 157,094,489 | 4,265,972,516 | **3,297,023 as recorded — invalid** |
| | | | | **≈35,731,920 reconstructed** |

**Cache TTL split (this materially changes cost and I could not have guessed it):**
- Main thread: **100% `ephemeral_1h`** (85,606,148 / 85,606,148). 1-hour writes bill at **2.0x**, not 1.25x.
- Subagents: **100% `ephemeral_5m`** (157,094,489 / 157,094,489). 1.25x is correct there.

**Subagent `output_tokens` is a stub, not a measurement.** Distribution across 32,032 subagent calls: min 1, p25 2, **median 3**, p75 7. 27,737 of 32,032 calls (86.6%) report ≤20 output tokens while the same records carry 1,000–3,000 characters of persisted assistant content. Subagent usage objects also lack the `iterations` array that main-thread objects carry. The writer appears to persist the `message_start` usage rather than the accumulated final usage.

**Reconstruction method (validated).** On the main thread, where output is real, I regressed context growth on its causes over 6,211 within-turn transitions (gap contains only tool results):

```
Δctx  =  0.9915·out_prev  +  0.4053·tool_result_chars  +  63.70·n_tool_results  +  0.19      R² = 0.9925
```

The `out_prev` coefficient of **0.9915 ≈ 1** proves billed output tokens re-enter the next prompt one-for-one. Adding persisted assistant *chars* as a fifth regressor gives it a coefficient of −0.005 — it explains nothing beyond `out_prev`. The tool-result rate is **0.4053 tok/char (2.47 chars/token)** plus **63.7 tokens fixed overhead per tool result** (block wrapper + system-reminder).

Inverting for the unknown: `out_est = Δctx − 0.4053·tr_chars − 63.70·n_tr`. Back-tested against known main-thread truth: **aggregate bias −0.84%** (15,246,251 estimated vs 15,375,126 actual), per-call median error −2%, p10/p90 −18%/+7%.

Applied to 31,128 of 31,173 possible subagent transitions (99.9% coverage): **34,772,351 tokens**. The 859 final-call outputs never re-enter any context and are unrecoverable; extrapolating at the mean gives **≈35.73M**. Refitting the coefficients on subagent data instead (0.3881 / 98.81) yields 35.44M — a 1.9% spread, so the number is robust to the calibration source. Subagent totals below use 35.73M; the final-answer extrapolation is the only estimated component and it is 2.7% of the subagent output figure.

**The recorded field understates subagent output by 10.8x.** Any analysis that trusts `output_tokens` in subagent transcripts is wrong by an order of magnitude on that line item.

---

## 3. Relative cost — `input×1 + cache_write×1.25 + cache_read×0.10 + output×5`

| | total | input | cache_write | **cache_read** | output |
|---|---|---|---|---|---|
| Main | 506,794,626 | 0.4% | 21.1% | **53.0%** | 25.4% |
| Subagent | 804,003,419 | 0.3% | 24.4% | **53.1%** | 22.2% |
| **Corpus** | **1,310,798,045** | **0.4%** | **23.1%** | **53.0%** | **23.5%** |

**Cache read dominates at 53.0% — 2.26x the next-largest line item.** Fresh input is a rounding error at 0.4%. Cache write and output are near-tied at 23.1% and 23.5%.

Subagents are **61.3%** of corpus cost against 38.7% for the main thread, despite being "cheap" delegated work.

With TTL-correct multipliers (main writes are 1-hour = 2.0x), the corpus total rises to **1,375,002,656 (+4.9%)** and main-thread cache_write climbs from 21.1% to 30.0% of main cost. **The prescribed 1.25x understates main-thread cache-write cost by 60%.**

---

## 4. The re-read multiplier

Two defensible formulas; they disagree, and the disagreement is itself informative.

**(a) Cache-ledger.** A token is written once (`cache_creation`) and served back `R` times (`cache_read`):

```
R = cache_read / cache_creation
```

Main **31.39**, subagent **27.16**, corpus **28.65**. Using `cache_read / (cache_creation + input)` instead: 30.59 / 26.75 / **28.11** — fresh input is too small to matter.

**(b) Context-ledger.** Count distinct tokens that ever entered context, per session, allowing for compaction:

```
D      = ctx₀ + Σ max(0, ctxᵢ − ctxᵢ₋₁)          where ctxᵢ = inputᵢ + cache_writeᵢ + cache_readᵢ
P      = Σ ctxᵢ                                   (all prompt tokens processed)
R_ctx  = P / D − 1
```

| | D (distinct) | P (processed) | processed per token | **re-reads** |
|---|---|---|---|---|
| Main | 54,864,325 | 2,775,281,445 | 50.58x | **49.58** |
| Subagent | 149,300,886 | 4,425,445,462 | 29.64x | **28.64** |
| **Corpus** | **204,165,211** | **7,200,726,907** | **35.27x** | **34.27** |

The gap between (a) and (b) on the main thread — 31.4 vs 49.6 — is real and quantifiable: `cache_creation / D` = **1.56 for main**, 1.05 for subagents. Main-thread content is written into the cache **1.56 times on average**, i.e. despite the 1-hour TTL, over a third of main-thread cache writes are re-warming content that had already been cached and expired between turns. Subagents run to completion fast enough that their 5-minute cache barely re-warms at all.

I report **34.27 corpus-wide** as the answer, because it counts distinct tokens rather than cache-write events.

---

## 5. Static floor per call

Derived as the prompt size of the **first API call of each session**, minus the first user prompt converted at the calibrated 0.4053 tok/char. Injections (CLAUDE.md, memory attachments) are kept *in* the floor, since they are re-sent on every call.

| Scope / model | sessions | min ctx₀ | median ctx₀ | floor (minus user prompt), min / median |
|---|---|---|---|---|
| Main, opus-4-8 | 133 | 68,469 | 84,579 | 68,326 / **84,478** |
| Main, opus-5 | 21 | 96,174 | 101,181 | 95,952 / **101,003** |
| Main, fable-5 | 3 | 77,552 | 90,969 | 77,401 / 90,890 |
| Sub, opus-4-8 | 692 | 14,609 | 54,059 | 13,391 / **52,797** |
| Sub, opus-5 | 133 | 58,799 | 66,842 | 56,041 / **64,527** |
| Sub, haiku-4.5 | 23 | 12,694 | 14,453 | 11,384 / **13,477** |

**Hard empirical bound** — the smallest prompt on *any* call in the corpus: main **68,469**, subagent **12,694**.

So: a main-thread call costs **~85,000 tokens before anything is said** (8,500 relative units if served from cache, 106,250–170,000 if the floor has to be re-written). A subagent starts at ~53,000 on opus, ~13,500 on haiku — the haiku figure shows the floor is dominated by tool definitions and system prompt, since those subagents get a reduced tool set.

**Floor × calls = 2,595,720,841 tokens, or 36.0% of all 7.20B prompt tokens ever processed** (main 30.4%, subagent 39.6%). Over a third of everything this corpus paid to read was the same unchanging preamble.

---

## 6. Decomposition of accumulated context

Done in **exact token arithmetic**, not char estimates: for each transition, the assistant's footprint is its known `out_prev` (validated at coefficient 0.99 above), and the residual `Δ − out_prev` is split across tool results / user messages / injections by their character shares. The `min(out_prev, Δ)` cap engaged in only 15 of 9,591 main transitions and absorbed 0.02% of growth.

**Main thread** — D = 54,864,325; static floor Σctx₀ = 13,427,968 (**24.5% of D**); growth = 41,436,357:

| category | tokens | % of growth | % of D |
|---|---|---|---|
| **assistant's own prior output** | 25,436,147 | **61.4%** | 46.4% |
| tool results | 10,591,461 | 25.6% | 19.3% |
| injections (attachments/system) | 2,724,757 | 6.6% | 5.0% |
| user messages | 2,683,992 | 6.5% | 4.9% |

By gap type: tool-loop 53.5%, mixed 32.8%, user-turn 13.7%. Eight transitions had negative deltas totalling −4,323,827 tokens — compaction or `/clear`.

**Subagents** — D = 149,300,886; floor = 47,146,458 (**31.6% of D**); growth = 102,154,428:

| category | tokens | % of growth | % of D |
|---|---|---|---|
| **tool results** | 67,218,080 | **65.8%** | 45.0% |
| assistant output | 34,919,746 | 34.2% | 23.4% |
| user messages | 15,697 | 0.0% | 0.0% |
| injections | 904 | 0.0% | 0.0% |

**The two scopes invert.** Main-thread context is 61% the model re-reading itself; subagent context is 66% tool output. Subagents get one prompt and never hear from the user again — user + injection is 0.02% of their growth.

### Content present in billing but absent or emptied in the transcript

**1. Emptied thinking blocks.** `thinking: ""` with an intact `signature`: **4,707 of 9,023 main blocks (52.2%)** and **6,083 of 19,383 subagent blocks (31.4%)**. The tokens were generated, billed, and re-sent; only the text is gone.

**2. Summarized thinking — larger than (1) and easy to miss.** Even where thinking text *is* present, it is a summary. Persisted assistant characters per billed output token, main thread: **1.66** where all thinking blocks are non-empty, 2.31 where the call has no thinking block at all, 0.74 where thinking is emptied. Nothing tokenizes at 1.66 chars/token. Confirmed not to be multi-iteration billing — every main-thread call has exactly one entry in `usage.iterations` (histogram: `{1: 9756}`).
**Handling:** I never used character counts as a proxy for the assistant's footprint. The regression showed `out_prev` carries it at coefficient 0.9915 and persisted chars add nothing (−0.005), so `output_tokens` is the correct measure and the summarization is invisible to the cost model. A char-based decomposition would have understated the assistant category by roughly half.

**3. System prompt and tool definitions.** Never appear in the transcript in any form. Only observable as the ctx₀ floor in §5 — 36% of all prompt tokens, entirely invisible to a content-level reading of these files.

**4. Subagent `output_tokens`.** The billing field itself is stubbed. Handled by reconstruction (§2).

**5. `<persisted-output>` files — the opposite direction, and a trap.** 97 files / 33.5 MB under `tool-results/`. The transcript's tool_result contains a stub: `"Output too large (29.5KB). Full output saved to: …/b4idqlg3h.txt\n\nPreview (first 2KB):"`. The ~2KB stub is what the model actually saw; the 30KB file was **never billed**. I verified size correspondence on `b4idqlg3h.txt` (30,222 bytes vs a 29.5KB claim and a 2KB preview) and confirmed the reference lives in a subagent transcript, not the parent. **These 33.5 MB are excluded from all totals.** Folding them in would inflate tool-result tokens by roughly 13.6M.

---

## 7. Where cost is concentrated

Per parent session, with subagents attributed to their spawning session, prescribed formula, reconstructed subagent output:

| rank | share | cumulative |
|---|---|---|
| #1 `b5382f8e-e7c` | 7.6% | 7.6% |
| #2 `44a9ffb6-fab` | 3.2% | 10.8% |
| #3 `670a5ade-41b` | 3.2% | 14.0% |
| #10 | 1.6% | 26.9% |
| #20 | 1.2% | 40.2% |
| #50 | 0.8% | 67.8% |
| #157 (last) | 0.005% | 100% |

- Top 10% of sessions (15) = **33.9%** of cost
- Top 20% (31) = **51.8%**
- Top 50% (78) = **84.5%**
- **Gini = 0.509**

**There is no single dominant cost driver — it is a heavy-headed long tail.** The largest session is only 7.6% of the corpus; you would have to kill the top 31 of 157 sessions to halve spend.

**The actual concentration is structural, not per-session.** Three findings outrank session skew:

1. **Subagents are 61.4% of total cost.** The top session ran 287 main-thread calls and **3,302 subagent calls**; 71.2% of its cost was subagent. Session #10 is 64.2% subagent, #20 69.3%, #50 71.8%. Sessions that fan out heavily are exactly the expensive ones.
2. **Cache read is 53.0% of everything**, 2.26x the next line item — and it is the *cheapest* per-token rate in the schedule. It dominates purely on volume: 6.95B tokens re-read.
3. **36.0% of all prompt tokens processed are the static floor** — system prompt and tool definitions re-read 41,788 times, never varying.

---

## Reproduction notes

Every number above comes from streaming `json.loads` per line with `python3 -c`/heredoc; no transcript was read whole. Pipeline: (1) drop repeat `uuid`; (2) group by `requestId`, taking `usage` from the first record and unioning content blocks across all records in the group — **omitting the union step silently discards most assistant content, since blocks are split across records**; (3) drop `model == "<synthetic>"`; (4) calibrate the tool-result rate on main-thread within-turn transitions by OLS; (5) invert for subagent output. Calibration constants: **0.4053 tokens/char** for tool-result content, **63.70 tokens** fixed per tool result, **0.9915** for `out_prev` (R² = 0.9925, n = 6,211).

**Not derivable from this data**, stated rather than estimated: the composition of the static floor (system prompt vs tool schemas vs CLAUDE.md) — only its total is observable; the 859 subagent final-answer outputs, which never re-enter any context (extrapolated at the mean, 2.7% of the subagent output figure); and the full unsummarized thinking text, which is billed but never written to disk.