Analysis complete. Report follows.

---

# Autopsy: six PR-review sessions (salesagent)

**Sessions studied** (all six are PR reviews; the top four untitled sessions turned out to be reviews too — I checked their first user prompt):

| Session | File (in `/Users/quantum/.claude/projects/-Users-quantum-Documents-ComputedChaos-salesagent/`) | Real API calls (main / sub) | Subagents | Relative cost |
|---|---|---|---|---|
| PR #1417 | `b5382f8e-e7c5-406b-b0db-6fef515a7c11.jsonl` | 293 / 3,302 | 68 | 99.3M units |
| PR #1493 | `6e0140a5-76e0-4561-8281-646e7949c06f.jsonl` | 172 / 591 | 16 | 25.1M |
| PR #1247 | `025c9bdf-2f91-461d-9719-85a22bcbdfae.jsonl` | 164 / 435 | 12 | 23.3M |
| PR #1399 | `1834ae34-e69a-41d0-b41a-488840bc9155.jsonl` | 87 / 681 | 15 | 18.0M |
| PR #1401 | `ea34d4fe-2dab-42a4-aeb6-8ef378888d48.jsonl` | 95 / 279 | 8 | 12.9M |
| PR #1481 | `7f661251-2b84-4ce2-84d3-cbabd2a4104f.jsonl` | 99 / 333 | 8 | 12.6M |

Cost units = `input×1 + cache_write×1.25 + cache_read×0.1 + output×5`, base input = 1. Total across six: **191M units**.

## Three corrections to the corpus baseline — they change the framing

**1. `measure.py` counts each API call ~3x.** Claude Code writes one JSONL record per *content block* (thinking, text, each tool_use), and every one of them carries a copy of the same `usage` object. Deduping by `requestId`: 856 "turns" in PR #1417 is **293 real API calls** (factor 2.9); PR #1399 is 296 → 87 (factor 3.4). The "181 calls per session" figure is roughly 62 real main-thread calls.

**2. Subagent tokens were excluded entirely.** `measure.py` globs `{D}/*.jsonl`, top level only. Subagent transcripts live one level down in `<session-id>/subagents/agent-*.jsonl`. Across these six sessions subagents are **5,621 of 6,531 real API calls (86%) and 61% of billed cost** — 116.6M of 191M units. These two errors partly cancel in the corpus total, but not per session: PR #1399's reported 3.9M billed is really 1.0M main + 2.3M subagent.

**3. The static floor is ~80k, not 27k.** Fitting context against transcript content across the four sessions with no compaction gives a per-call constant of **77k–85k tokens** (system prompt + tools + CLAUDE.md + skills), RMS error 3–6k on contexts of 100–730k. Subagents start at a **~46–50k** floor. Median main-thread context per real call is 240k–565k, not 193k; peak observed 732k (PR #1493, call 172).

---

## 1. Where the tokens went

Corpus-wide across the six, by billed line item: **cache read 55%, cache write 26%, output 18%, fresh input 1%.**

Attribution of *context re-read* — computed as size × number of subsequent API calls, calibrated at 3.8 chars/token by least-squares against actual usage (RMS 3–6k tokens):

| Contributor | PR #1493 | PR #1401 | PR #1247 | PR #1481 |
|---|---|---|---|---|
| **Reasoning tokens (not stored in transcript)** | 47% | 49% | 54% | 41% |
| **Static floor × calls** | 20% | 23% | 14% | 30% |
| Bash results | 8.0% | 4.4% | 4.9% | 6.0% |
| Injected attachments / system-reminders | 6.4% | 4.0% | 3.1% | 7.3% |
| User prompts (incl. task-notifications) | 4.4% | 3.4% | 13.1% | 3.4% |
| Assistant prose | 4.0% | 3.6% | 3.1% | 3.2% |
| Read results | 3.4% | 6.9% | <1% | 5.8% |
| Agent prompts + Agent reports | 5.6% | 6.4% | 7.0% | 5.3% |

**The biggest single line is invisible in the transcript.** `thinking` blocks are persisted with `"thinking": ""` and a 3KB signature — the text is stripped. Derived as `output_tokens − visible_output/3.8`, reasoning is **75–84% of all main-thread output** (2.41M tokens across the six) and it never leaves context: context grows monotonically across user-turn boundaries in every non-compacted session, so every reasoning block is re-read by every later call in the session. That is what makes long sessions super-linear rather than linear.

File reads and diffs — the things one intuitively blames — are 3–7% each.

## 2. Biggest single context contributors

There is no whale. The largest single item in any of these sessions is 9.5k tokens. Cost is a long tail of 2–7k-token items each re-read 90–290 times:

- **PR #1247**: the `update-config` skill body injected as a user prompt — **39.4k tokens, re-read 110 times = 4.34M tokens**. Single largest item found in the corpus.
- **PR #1417**: a `Write` of a scratchpad review file, 9.0k tokens × 239 re-reads = 2.15M. Then eight `Agent` dispatch prompts at 4.1–5.6k each (`review-spec-conformance on #1417`, `review-test-integrity on #1417`, …), 1.1–1.4M each.
- **PR #1493**: `Read` of `tests/bdd/test_uc018_list_creatives.py` (4.5k tokens × 160 = 0.72M); `Read` of `.claude/rules/private/review-charter.md` (2.8k × 171 = 0.48M).
- **PR #1481**: `Read` of `src/core/tools/creative_formats.py` (7.1k × 94 = 0.67M); `gh pr diff 1481` (2.2k × 95 = 0.21M).
- **Every session**: `<task-notification>` blocks — subagent completion reports injected into the main thread — 2.9–7.2k tokens each, 5–12 of them per session, each re-read for the remainder of the session.

Aggregated, **subagent coordination surface** (Agent params + Agent results + task-notifications) is 21–22% of main-thread visible context in the small sessions and **50% in PR #1417, 42% in PR #1399**.

## 3. Re-derivation

Counting exact-match repeats of `Bash` commands and `Read` paths across the main thread *and* all subagents of the same session:

| Session | Tool results | Redundant re-fetch |
|---|---|---|
| PR #1417 | 4,889 | 1,965k of 3,960k tokens — **50%** |
| PR #1493 | 1,088 | 402k of 858k — **47%** |
| PR #1481 | 560 | 157k of 364k — **43%** |
| PR #1399 | 1,068 | 328k of 785k — **42%** |
| PR #1247 | 757 | 205k of 717k — **29%** |
| PR #1401 | 513 | 55k of 279k — **20%** |

The pattern is not the main thread re-checking itself; it is **every subagent independently bootstrapping from the same files**:

- `.claude/rules/private/review-charter.md` — read by **53 different agents** in PR #1417 (149.5k tokens), 17 in PR #1493, 10 in PR #1399, 8 in PR #1401.
- `.claude/rules/private/reviewer-tooling*` — 47 agents in PR #1417 (70.1k).
- Individual memory files under `~/.claude/projects/…/memory/` — one file read by 42 agents, another by 41, another by 31, in PR #1417 alone.
- Source files: `src/core/exceptions.py` 35 times across 22 agents; `src/core/schemas/_base.py` 45 times across 22; `tests/bdd/conftest.py` 18 times across 5 agents in PR #1399.

Bootstrap reads (rules / memory / CLAUDE.md / skills) are **9–34% of all subagent tool calls** — 805 calls and 1,076k tokens in PR #1417.

The multiplier: the suite is re-run in waves. PR #1417 spawned the same 8 reviewer roles three times over (`review-code-patterns`, `review-error-wire`, `review-spec-conformance`, `review-architecture-guards`, `review-test-integrity`, `review-bdd`, `review-security` each ×3, plus 38 follow-up agents); PR #1493 ran its suite twice. Every wave re-pays the full bootstrap plus the 46–50k prefix.

## 4. Turn efficiency

Error rates are low (1–2%) and immediate retries are rare. The calls are not wasted on failure — they are wasted on being *cheap payloads carried on an expensive vehicle*:

| Session | Main tool calls | Median result | Results <200 tok | Median context | Ratio |
|---|---|---|---|---|---|
| PR #1247 | 149 | 158 tok | **55%** | 565k | 1 : 3,565 |
| PR #1493 | 170 | 211 tok | 47% | 410k | 1 : 1,941 |
| PR #1417 | 296 | 242 tok | 39% | 452k | 1 : 1,865 |
| PR #1399 | 136 | 209 tok | 49% | 240k | 1 : 1,149 |
| PR #1481 | 94 | 242 tok | 44% | 280k | 1 : 1,156 |
| PR #1401 | 99 | 234 tok | 36% | 321k | 1 : 1,371 |

Subagent calls are 4–15x more efficient on this measure (median result 240–597 tokens against a 103–133k context, ratio 1:200–1:430), because their context is short-lived.

**Measured cost of the small calls:** across the six sessions, 421 main-thread calls returned under 200 tokens; the API call that carried each one cost **21.2M units — 36% of all main-thread input cost, 11% of total session cost.**

Also driving turn count: PR #1399 spent 28 of 136 main calls on `TaskCreate`/`TaskUpdate` bookkeeping, each one paying a 240k context re-read to record a status change.

**One more mechanism, separate from turn count.** Cache writes are 26% of cost. In PR #1417 that is 7.9M tokens, **80% of it in just 16 calls** — full-context rewrites after the prompt cache expired. 13 of those 16 followed an idle gap over 5 minutes; several followed multi-day gaps (5,681 min, 8,908 min, 5,308 min). The session spans 474 wall-clock hours. The rewrite at call 231 cost **812k cache-write tokens (1.02M units) before any work happened**. Across the six sessions, >5-minute-gap rewrites total 12.26M cache-write tokens = **15.3M units, 8% of everything**, and account for 7–36% of each session's input cost.

## 5. The anatomy of an expensive review

1. **A long-lived main thread accumulates and never forgets.** Context climbs 75k → 730k. Nothing is evicted, including reasoning tokens that are 75–84% of output and roughly half of everything re-read.
2. **The main thread's job becomes dispatch and bookkeeping, at maximum context.** Half its calls return under 200 tokens, each paying 240–565k. Agent prompts, task-notifications and consolidation `Write`s are its largest resident items.
3. **The fan-out is where the money actually is** — 61% of cost, 86% of API calls. Each subagent averages **0.92M units**, versus 12.4M for an entire main-thread session body. Eight reviewers ≈ two-thirds of a whole main thread. PR #1417's 68 agents cost 2.5x its own main thread.
4. **Each agent re-derives the shared premise.** 39% of subagent context is the 46–50k static prefix re-read across ~40 short calls; 9–34% of its tool calls re-read the charter, the reviewer-tooling rules and the same memory files every sibling agent just read. 20–50% of all tool-result tokens in a session are re-fetches.
5. **The session is resumed across days, and each resume rewrites the whole context at 1.25x.**

---

## Three highest-leverage changes, ranked by measured tokens saved

### 1. Make each subagent cheap, and cap waves — 116.6M units (61% of cost), ~0.92M per agent

The dispatch decision, not the review depth, sets the bill. Two sub-levers with independent measured bases:

- **Push the bootstrap into the prompt.** 3.1M tokens of raw duplicate fetches across the six sessions, amplified by ~40 re-reads each ≈ 124M tokens ≈ **12.4M units (6.5%)**. The charter and the memory files are already resident in the main thread's context and already paid for; 53 agents reading `review-charter.md` separately is pure re-purchase. Inline the ~3k-token charter and the relevant memory excerpt in the Agent prompt (the CLAUDE.md dispatch rule already mandates a Step 0 read list — make it a paste, not a read).
- **Don't re-run the suite in waves.** PR #1417 ran the 8-role suite three times; PR #1493 twice. A second wave re-pays the prefix (46–50k × ~40 calls per agent), the bootstrap, and the same source-file reads. Halving agent count across these six saves ~58M units (30%); dropping just the repeat waves saves ~35M (18%).

### 2. Batch main-thread tool calls — 21.2M units (11% of cost)

421 main-thread calls returned under 200 tokens. In PR #1247 the median call added 158 tokens and re-read 565k — 1:3,565. The composite-`Bash` style already present in these transcripts (`echo "=== PR VIEW ===" && gh pr view … && gh pr diff …`) is the right instinct applied to only some of the calls. Every additional call late in a session costs the full current context, so the rule is: **anything below ~1k tokens of expected output belongs in a batch, and status bookkeeping does not belong in the main thread at 500k context at all.**

### 3. Never resume a large-context session after a gap — 15.3M units (8% of cost)

36 full-context rewrites across the six sessions, 12.26M cache-write tokens, priced at 1.25x. PR #1417 was resumed after 3.9 days and 6.2 days into contexts of 510k and 704k; each resume cost more than a small review session's entire main thread. Finish a review in one sitting, or end it and start a fresh session from a written handoff — a 700k-token resume costs ~875k billed tokens before the first useful token. Note also that 3 of PR #1417's 16 rewrites followed gaps under 2 minutes, meaning something invalidated the prefix mid-flow; I did not determine what.

---

## What I could not measure

- **Reasoning text is not in the transcripts** (`thinking` blocks are stored empty with a signature). Its volume is derived as `output_tokens − visible_output_chars/3.8`. The 3.8 chars/token constant is fitted, not measured directly; the fit's residual is 3–6k tokens against contexts of 100–730k in the four non-compacted sessions, which is why I trust it there.
- **PR #1417 and PR #1399 contain compaction events.** My amplification model does not reset at a compaction boundary, so their per-category percentages are over-credited (the model reported >100% for reasoning, the tell). Their absolute usage figures and re-derivation counts are unaffected; only the category shares are approximate. The four clean sessions carry the attribution table.
- **Pricing weights are assumed** (1 / 1.25 / 0.1 / 5). Different real weights shift the shares but not the token counts or the ranking of levers 1 and 2.
- **The 5-minute cache TTL is assumed**, not verified in this environment. What I measured is the correlation: 29 of 36 large cache-write events followed an idle gap over 5 minutes.
- I did not attribute cost inside the `<system-reminder>` and injected-attachment stream beyond its 3–7% share — the injected text differs from what the transcript stores, so its true size is a lower bound.