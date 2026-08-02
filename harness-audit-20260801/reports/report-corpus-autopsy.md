I have what I need. Here is the report.

---

# Corpus-wide autopsy: 159 sessions

**Method note.** Everything below comes from structural JSONL parsing (`python3 -c` / heredoc), deduped by `requestId`, subagents included via `<session-id>/subagents/*.jsonl`. No transcript was read whole. Cost units = `input + 1.25·cache_write + 0.10·cache_read + 5·output`.

**Reproduction check:** my independent pass yields 41,851 calls / 1,148.6M units vs FACTS' 41,859 / 1.15B — 0.02% apart. The corpus totals in FACTS are sound.

---

## 1. Classification — reviews dominate even harder than assumed

Classified by first user prompt + `custom-title`, then validated against actual `Task` dispatch types.

| class | n | total | % cost | median | mean | max |
|---|---|---|---|---|---|---|
| PR-review | 68 | 556.0M | 48.4% | 4.18M | 8.18M | 88.3M |
| PR-rereview | 65 | 527.4M | 45.9% | 7.29M | 8.11M | 26.4M |
| issue-triage | 17 | 50.0M | 4.4% | 2.26M | 2.94M | 13.6M |
| other | 5 | 6.6M | 0.6% | 0.32M | 1.32M | 4.0M |
| research | 1 | 5.1M | 0.4% | — | 5.06M | 5.1M |
| implementation | 3 | 3.6M | 0.3% | 0.53M | 1.18M | 2.7M |

**PR work = 133/159 sessions and 94.3% of cost.** The pass-1 assumption holds and then some. Cross-checked structurally: 120 sessions dispatched ≥1 `review-*` lens and carry 94.1% of corpus cost; the other 39 sessions total 67.3M (5.9%), median 0.69M.

Note the **rereview median (7.29M) is 74% above the first-review median (4.18M)**. Re-reviews are the more expensive half despite being nominally incremental — they re-pull all four feedback surfaces and re-run the panel against a diff that already passed once.

Dispatch census (851 total, 11 distinct types): 759 are `review-*` (89.2%), 68 `general-purpose`, 20 `Explore`, 4 untyped. FACTS' "738" counts the 7 core lenses; adding `review-admin-ui` gives 759.

---

## 2. Concentration — the 40% figure is close but cost is *less* concentrated than pass 1 implies

| slice | cost | % of total |
|---|---|---|
| top 1% (n=1) | 88.3M | 7.7% |
| top 5% (n=8) | 287.5M | 25.0% |
| **top 10% (n=16)** | **422.9M** | **36.8%** |
| top 20% (n=32) | 627.2M | 54.6% |
| top 50% (n=80) | 980.0M | 85.3% |
| bottom 50% (n=79) | 168.6M | 14.7% |

Top-10%-is-40% → **actually 36.8%**. Directionally right. But the tail is fat: the bottom half still carries 14.7%, so there is no fix that works purely by taming outliers.

**Cost of a PR review** (the 120 lens-running sessions):

| p10 | p25 | **median** | p75 | p90 | worst |
|---|---|---|---|---|---|
| 2.44M | 3.75M | **6.65M** | 10.71M | 17.02M | 88.30M |

**Worst/median = 13.3x. But p90/median is only 2.6x** — the spread is driven by a handful of genuine monsters, not by a broadly heavy distribution. Fixing the median review is a different project from fixing PR #1417.

---

## 3. The modes the 6-session sample missed

### 3a. Main-thread-dominated sessions — the biggest miss

Pass 1's story is subagent bootstrap. Corpus-wide the split is main 506.8M (44.1%) / subagent 641.8M (55.9%) — but **that average hides a distinct mode**, and it contains the #2 and #3 most expensive sessions:

| session | cost | nsub | main | sub | sub% | what |
|---|---|---|---|---|---|---|
| `670a5ade` | 39.1M | 11 | **32.2M** | 6.8M | **18%** | PR #1669 CI fix |
| `44a9ffb6` | 40.4M | 20 | **23.7M** | 16.7M | **41%** | norbert deployment tasks |
| `b9324151` | 24.6M | 6 | 13.5M | 11.2M | 45% | PR #1719 rereview |
| `afb24d91` | 4.84M | **0** | 4.84M | 0 | **0%** | skills-extraction status |

`afb24d91` is the pure case: **100 API calls, zero subagents, 4.84M units.** Tool mix Bash 70 / Edit 60 / Read 15 / Write 11; context grew 92k → 469k; 21.2% of its cost is output tokens. No subagent bootstrap anywhere in it. A fix aimed at agent prefixes does nothing for this session.

**Mechanism, measured.** Per-call main-thread context (`cache_read + cache_write + input`), 9,791 calls:

| p10 | p25 | p50 | p75 | p90 | p95 | p99 | max |
|---|---|---|---|---|---|---|---|
| 114k | 167k | **247k** | 356k | 499k | 614k | 831k | 996k |

976 calls (10.0%) run above 500k context, carrying 63.0M units in cache-read alone. Worst main threads by peak: `44a9ffb6` 995,677 (median 478k across 309 calls), `670a5ade` 949,711 (median 504k across 494 calls), `b5382f8e` 910,970, `025c9bdf` 903,841.

This is a **long-conversation** failure mode, not a fan-out failure mode. It coexists with the subagent mode and needs a different remedy.

### 3b. Bootstrap is only 8.9% of subagent cost — pass 1's framing is misleading

Measured over all 859 subagent transcripts: the **first call** of each agent totals 56.9M units = **8.9%** of the 641.8M subagent cost. Subagents run a **median of 31 calls each** (mean 37.3, p90 67, max 179); **zero are one-shot**.

So "bootstrap" is not a one-time charge — it's a prefix re-shipped on every one of ~31 calls. Correct decomposition:

**Subagents (641.8M):**
- immutable prefix re-read — **285.7M (44.5%)**
- accumulated own work — **339.7M (52.9%)**
- output incl. reasoning — 16.5M (2.6%)

**Main threads (506.8M):**
- immutable prefix re-read — 111.6M (22.0%)
- accumulated conversation — **266.4M (52.6%)**
- output incl. reasoning — **128.8M (25.4%)**

**Corpus rollup:**

| | units | % |
|---|---|---|
| prefix re-read (static, per call) | 397.3M | **34.6%** |
| accumulated context re-read | 606.1M | **52.8%** |
| output + reasoning | 145.3M | 12.7% |

Prefix (method: per-thread floor = `min(context)` across its calls) totals **1.75 billion tokens shipped**. Median floor: 55,045 tok subagent, 86,326 tok main.

### 3c. The model re-reading its own prior turns rivals tool results

Attributing accumulated carry as `payload_tokens × calls_it_persists_through × 0.10`, over all 1,018 threads:

| source | units | % of carry | % of corpus |
|---|---|---|---|
| tool results | 169.0M | 49.9% | 14.7% |
| **model's own prior turns** | **157.6M** | **46.6%** | **13.7%** |
| user messages | 11.8M | 3.5% | 1.0% |

Pass 1 looked exclusively at tool results. **Nearly half the accumulated cost is the model re-reading its own output — including the invisible reasoning tokens of FACTS trap #3.** No amount of `jq`-trimming touches this.

### 3d. "No single whale" survives, but only because Read truncates

Total tool-result payload across the whole corpus is **186.1 MB = 49.0M tokens**, against 6.95B cache-read tokens — a **142x re-read multiplier** on tool output. Read results average 1,656 tokens (11,846 full-file vs 4,461 with `limit`); Bash results average 553.

I initially flagged `src/core/tools/media_buy_create.py` (235,855 B, 243 reads, 33 sessions) as a whale by file-size×count. **That was wrong** — measuring actual `tool_result` payloads, its true carry cost is 0.74M units. The Read tool truncates. Pass 1's "no single whale" holds.

Real carry ranking: `BASH: cd` 47.15M · `review-charter.md` 13.69M · `BASH: echo` 4.87M · `reviewer-tooling.md` 4.18M · `reference_review_patterns.md` 3.87M.

**This is a material correction to pass-1 emphasis.** FACTS frames the charter as "~10M tokens of unchanged text." Measured, charter + reviewer-tooling contribute ≈21M units total (13.69M + 4.18M carry, plus ~7.7M first-ingest at cache-write) — **about 1.8% of corpus cost.** Real, worth fixing, but not the headline lever.

---

## 4. Compaction — fires 6 times, saves money every time, and is badly under-used

**Every compaction event in 159 sessions:**

| # | session | rank by cost | trigger | preTokens | postTokens | duration |
|---|---|---|---|---|---|---|
| 1 | `1834ae34` | #14 | manual | 365,916 | 7,849 | 86s |
| 2 | `1912d5d4` | #20 | manual | 454,240 | 8,164 | 96s |
| 3 | `1912d5d4` | #20 | manual | 461,628 | 8,353 | 90s |
| 4 | `44a9ffb6` | **#2** | **auto** | 1,000,206 | 10,422 | 119s |
| 5 | `670a5ade` | **#3** | **auto** | 954,472 | 9,379 | 90s |
| 6 | `b5382f8e` | **#1** | manual | 912,697 | 13,901 | 246s |

**6 events, 5 sessions = 3.1% of the corpus.** Only 2 were auto-triggered. Zero subagent transcripts ever compact.

**Does compacting make a session cheaper?** Measured directly — actual post-boundary cost vs. the counterfactual of every subsequent call running at `preTokens`:

| session | calls after | actual | counterfactual | **saved** |
|---|---|---|---|---|
| `670a5ade` | 247 | 10.2M | 23.6M | **13.4M** |
| `44a9ffb6` | 127 | 4.7M | 12.7M | **8.0M** |
| `b5382f8e` | 45 | 0.9M | 4.1M | **3.2M** |
| `1912d5d4` (×2) | 127 + 58 | 4.0M | 8.5M | **4.5M** |
| `1834ae34` | 54 | 1.2M | 2.0M | **0.7M** |

**Total measured saving: 29.8M units from 6 events.** Compaction is a *symptom* of expensive sessions and also a *cure* — and it is invoked in 3% of them. 42 main threads peaked above 400k without ever compacting; median main-thread peak is 322,785 tok, against an `autoCompactWindow` of 985,000. **The window is set roughly 3x too high to ever engage for typical sessions.**

Upper bound on capping main-thread context (excess above cap × 0.10; ignores compaction's own cost and information loss):

| cap | calls over | upper-bound saving | % corpus |
|---|---|---|---|
| 200k | 6,334 (65%) | 102.6M | 8.9% |
| 300k | 3,603 (37%) | 53.8M | 4.7% |
| 400k | 1,826 (19%) | 27.7M | 2.4% |

**Could not measure:** the compaction operation's own cost. Context drops 949,711 → 96,511 with **no billed assistant record between the two** — the summarization call is not written to the transcript. Every saving above is therefore gross, not net. The true net is lower by whatever ~950k tokens of summarization input costs, six times.

**Methodological byproduct:** an additive context model (prefix + Σ assistant output + Σ tool results) validates to **−17.9%** on `025c9bdf`, which never compacted, but over-predicts by 99–384% on `44a9ffb6`, `670a5ade`, and `b5382f8e` — all of which did. The over-prediction *is* the dropped context. That the un-compacted case under-predicts is also weak evidence that assistant output (including stripped thinking) genuinely persists in context rather than being elided, which is what makes 3c defensible.

---

## 5. Cross-session redundancy — the memory protocol is a round-trip tax, not a byte tax

Scanned all 1,018 transcripts: 16,307 Read calls over 2,258 distinct paths; 38,535 Bash calls over 37,707 distinct command strings.

**Files read in the most distinct sessions (of 159):**

| sessions | reads | file |
|---|---|---|
| 110 | 484 | `memory/feedback_trace_flows_not_claims.md` (3,404 B) |
| 110 | 466 | `memory/feedback_detecting_subagent_overconfidence.md` (6,010 B) |
| 107 | 435 | `memory/feedback_truth_over_optimism.md` (7,174 B) |
| 106 | 428 | `memory/feedback_complete_claim_requires_full_pattern_enumeration.md` (2,646 B) |
| 105 | 404 | `memory/feedback_verify_before_asserting.md` (6,874 B) |
| **99** | **586** | **`.claude/rules/private/review-charter.md` (39,867 B)** |
| 86 | 396 | `.claude/rules/private/reviewer-tooling.md` (13,627 B) |

**The memory directory is 8,098 Read calls — 49.7% of every Read in the corpus — for 9.4% of read bytes.** 113 distinct memory files touched; 169 files on disk totalling 525,937 B (≈138k tokens if concatenated). Nine separate files are each read in >100 of 159 sessions.

**This is the round-trip finding.** Marginal cost of one API call: **51.7k units on a main thread, 20.0k in a subagent** (506.8M/9,799 and 641.8M/32,060). A 2.6 KB memory file carries ~700 tokens of content but forces a full-context re-ship. **Content-to-round-trip ratio ≈ 1:17.** Eight thousand round trips to deliver 9.53M tokens of guidance that is, by construction, identical every time.

This is categorically different from in-session redundancy and needs a different fix: **a file read in 100 different sessions belongs in the prefix (paid once per call at cache-read, already amortized), not fetched by tool call (paid as a fresh round trip).** The current design has it backwards.

**Bash intent (compound-aware — does the command *contain* the verb, not just start with it):**

| intent | calls | % |
|---|---|---|
| git/gh state query | 23,166 | **60.1%** |
| file/text inspect | 8,780 | 22.8% |
| python/script | 4,092 | 10.6% |
| test run | 2,128 | 5.5% |
| other | 369 | 1.0% |

**Two corrections to pass 1 here.** (a) FACTS' "7,475 Bash calls" is **main-thread only** — I reproduce 7,475 exactly for main threads, but the corpus total including subagents is **38,535**. (b) The git/GitHub share is **60.1%, not 80%**, when measured across the full corpus.

Confirmed: 88.2% of commands are compound (`&&`/`;`/newline), 37,707 distinct strings for 38,535 calls — **near-zero exact repetition, so caching is useless; the repetition is in intent.** Normalizing (masking SHAs, numbers, paths) collapses only 37,707 → 33,044, so even intent-level dedup is limited. The dominant normalized forms are scratchpad/worktree path boilerplate: `cd /private/tmp/claude-501/…/scratchpad` (260), `export TMPDIR=…` (137, 113, 101), `WT=…` (66, 60). Absolute path boilerplate is **13.7% of all bash command characters** (4.8% scratchpad + 8.8% repo/worktree) — 0.63M tokens of pure addressing, re-read for the life of each thread. Average command is 453 chars / 119 tokens.

---

## 6. Trend — the harness got ~50% heavier in seven weeks, monotonically

Corpus spans **2026-06-12 → 2026-07-31**; 135 of 159 sessions are July.

The cleanest signal is the **prefix floor** (`min(context)` per thread) by week — it isolates harness weight from workload:

| week of | subagent median prefix | main median prefix | main median calls |
|---|---|---|---|
| 06-08 | 46,064 | 68,710 | 58 |
| 06-15 | 48,080 | 69,764 | 41 |
| 06-22 | 50,245 | 75,048 | 39 |
| 06-29 | 49,708 | 76,290 | 34 |
| 07-06 | 50,182 | 79,142 | 36 |
| 07-13 | 55,160 | 88,558 | 52 |
| 07-20 | 58,542 | 93,062 | 53 |
| 07-27 | **68,486** | **105,052** | **95** |

**Subagent prefix +48.7%, main prefix +52.9%, in seven weeks. Monotonic in both.** Main threads also got longer (58 → 95 median calls) and subagent median calls jumped 26 → 70 in the final week.

Cost per unit of work rose with it. Splitting the 120 lens-running sessions chronologically in half:

| | median session | mean | lenses/session | **cost per lens** |
|---|---|---|---|---|
| first half (06-13 → 07-14) | 5.58M | 8.65M | 6.6 | **1.31M** |
| second half (07-14 → 07-31) | 7.61M | 9.37M | 6.0 | **1.55M** |

**Cost per lens dispatch +18% while lenses per session fell 9%.** The harness is not doing more review — each unit of review got more expensive.

**Extrapolation.** Main prefix is growing ≈5.2k tok/week. Every call in every session pays it. At this rate the main prefix passes 150k around mid-October 2026 and 200k by year end; on a 95-call session that alone is ~1.0M units of pure floor. The trend, not any single artifact, is the thing to arrest.

---

## 7. Where the money actually is — and the one clean proof a fix exists

**`Explore` agents in this same harness boot at a median prefix of 14,464 tokens. Review lenses boot at ~54,000.**

Per-agent-type economics, joined via the `agent-*.meta.json` sidecars (which carry `agentType`, `toolUseId`, `spawnDepth` — a clean join key pass 1 didn't use):

| agentType | n | total | % sub | mean | median | calls/agent | med prefix |
|---|---|---|---|---|---|---|---|
| review-test-integrity | 128 | 103.1M | 16.1% | 0.81M | 0.64M | 40 | 54,003 |
| review-error-wire | 90 | 88.8M | 13.8% | 0.99M | 0.81M | 47 | 55,159 |
| review-spec-conformance | 112 | 87.6M | 13.7% | 0.78M | 0.74M | 39 | 54,680 |
| review-code-patterns | 121 | 84.3M | 13.1% | 0.70M | 0.57M | 35 | 55,514 |
| review-architecture-guards | 119 | 80.3M | 12.5% | 0.67M | 0.52M | 36 | 54,028 |
| review-bdd | 85 | 79.4M | 12.4% | 0.93M | 0.79M | 45 | 54,001 |
| review-security | 85 | 63.2M | 9.8% | 0.74M | 0.56M | 36 | 53,465 |
| general-purpose | 76 | 39.9M | 6.2% | 0.52M | 0.39M | 23 | 61,335 |
| review-admin-ui | 19 | 8.8M | 1.4% | 0.46M | 0.33M | 23 | 51,991 |
| **Explore** | 24 | 6.6M | 1.0% | 0.27M | 0.28M | 35 | **14,464** |

`review-*` = 595.4M = 92.8% of subagent cost = **51.8% of the entire corpus**. Note the lenses are remarkably *uniform* — 0.46M–0.99M mean, 52k–56k prefix. There is no rogue lens; the panel is evenly heavy. `review-error-wire` and `review-bdd` are the priciest mainly because they run more calls (47, 45) rather than heavier ones.

**Sizing the prefix lever:** ~29,559 review-lens API calls × (54,000 − 14,464) × 0.10 = **116.9M units = 10.2% of corpus.** Upper bound — it assumes the dropped 40k carries no value to the lens, which is certainly false. But `Explore` runs 35 calls/agent at 14.5k prefix and produces useful work, so the floor is demonstrably not physics.

**Prefix composition** — partially measurable: root `CLAUDE.md` 34,620 B (≈9.1k tok), `tests/CLAUDE.md` 18,676 B (≈4.9k tok), agent defs 4,594–14,453 B (≈1.2–3.8k tok). That accounts for ~15–18k of the 39.5k gap to `Explore`. **The remainder is system prompt + tool schemas, which I cannot separate from the transcript** — usage records report totals only. `Explore`'s restricted tool set (no Agent/Write/Edit) is the likely bulk of it, which would make **tool-schema surface, not prose, the larger half of the prefix.** That is testable but not from these transcripts.

Model mix, for completeness: `claude-opus-4-8` 75.9%, `claude-opus-5` 21.6%, `haiku-4-5` 1.3%, `fable-5` 1.2%. Spawn depth: 760 at depth 1, 3 at depth 2 — the panel is flat, not recursive.

---

## What I could not measure

- **Compaction's own cost.** No billed record exists between pre- and post-boundary. All six savings figures are gross.
- **Prefix internal composition below ~18k.** System prompt and tool-schema token counts are not separable from `usage` totals. The single largest remaining unknown, and it sits under 34.6% of corpus cost.
- **Per-lens attribution of the 3.8 chars/token calibration.** Inherited from FACTS with its 3–6k RMS error; it affects §3c/§5 payload figures but not §1/§2/§4/§6/§7, which use billed token counts directly.
- **Why the `update-config` skill body became a user prompt** in PR #1247. Not investigated — orthogonal to corpus-level structure and pass 1 already flagged the mechanism as unexplained.
- **Whether the 12 detectors are invoked.** Out of scope for this pass; the Bash census shows `python/script` at 10.6% of calls but I did not resolve which scripts.

## The three things that change the picture

1. **Prefix, not bootstrap.** Bootstrap is 8.9% of subagent cost; the prefix *re-shipped across 31 median calls* is 44.5%. Pass 1 named the right file and the wrong mechanism — and the charter itself is only ~1.8% of corpus.
2. **Two failure modes, not one.** Long single-threads (`670a5ade` at 82% main, `afb24d91` at 100% main) are immune to every subagent fix. They need context capping — and compaction, measured, saves 29.8M units across the 6 times it has ever fired, against an `autoCompactWindow` set ~3x too high to engage.
3. **The trend is the story.** +49% subagent prefix and +53% main prefix in seven weeks, monotonic, with cost per lens up 18%. Whatever is added next is paid on all ~42k calls of the next seven weeks.