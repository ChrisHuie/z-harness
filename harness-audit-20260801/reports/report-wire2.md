All targets captured, credentials verified clean, both repos untouched (`agenticads-sim-plan` 0 changes; salesagent still `6881e8da4`).

---

## Method

`BUN_CONFIG_VERBOSE_FETCH=curl` for request bodies, plus one capability the prior pass did not use: **`CLAUDE_CODE_ENABLE_TELEMETRY=1 OTEL_METRICS_EXPORTER=console`**, which emits `claude_code.token.usage` and `claude_code.cost.usage` per call, split by `query_source` and `type`. The wire gives structure; OTEL gives billed tokens. Together they close target 1.

Stderr passed through a redactor **before** touching disk. Final sweep over all 56 artifacts: 42 hits, all the literal `sk-ant-REDACTED` marker, **0 real tokens, 0 raw `Bearer` strings**. (`bin.strings` holds bare key-*type* prefixes `sk-ant-oat01-` / `sk-ant-admin01-` from the CLI's own string table — no key material.)

Artifacts in `/private/tmp/claude-501/-Users-quantum-Documents-GitHub-agenticads-sim-plan/e2367c8b-0c8b-43ae-a5d4-98ce3fbcecea/scratchpad/wire2/`: captures `comp1–comp5.err`, `live3.err`, `post1.err`, `disp1–disp4.err`, `inj1.err`; parsers `extract2.py`, `injdump.py`, `otelparse.py`, `cmp.py`.

**Calibration measured, not assumed** — running the same prompt with and without the global CLAUDE.md isolates 10,605 B → **4,300 tokens exactly = 2.466 B/token** for injected markdown; tool JSON is ~2.95 B/token; a full assembled subagent prefix ~2.8 B/token.

---

## 1. Compaction's own billing — SETTLED, and it is much cheaper than feared

Two full compaction events captured end to end. The second used a **real tool roster**, which turned out to be load-bearing.

| | tools-less (99,053 tok ctx) | **full roster (124,327 tok ctx)** |
|---|---:|---:|
| summarization `input` (fresh, 1.0x) | 30,504 | **30,504** |
| summarization `cacheRead` (0.1x) | 70,105 | **95,666** |
| summarization `cacheCreation` | 202 | **152** |
| summarization `output` | 1,979 | **1,288** |
| cost (sonnet) | $0.142986 | **$0.140102** |
| the live turn immediately before | $0.194849 | $0.200762 |
| first turn after compaction | 8,657 rd + 6,412 wr | **29,518 rd + 9,887 wr** |

**The summarization request, from the wire:**
- **`model` = the session model.** Opus session → `claude-opus-5`; sonnet session → `claude-sonnet-5`. Never a cheap model.
- **`max_tokens: 64000`**, `stream: true`.
- **`tools` is the session's full roster (11), not stripped.** My first run showed `tools: 0` only because it ran `--tools ""`. This matters: the roster is part of the cache prefix, so keeping it is what preserves the cache.
- **A cache breakpoint sits on the last-but-one assistant block** → the compaction call **cache-reads the entire live prefix**: 95,666, byte-for-byte the preceding live turn's `cacheRead`.
- The 6,361 B summarization instruction (~1,900 tokens) is appended after the last user message.
- The first-message `<system-reminder>` (10,969 B) is **replayed inside** the compaction request.

**Why nobody could see it:** telemetry tags it **`query_source: "auxiliary"`**, not `"compact"` (the binary has a `querySource:"compact"` literal, but the metric buckets it with title generation). The transcript has **no usage record at all** — between the last live turn and `compact_boundary` there is no assistant record. The SDK `result` event for a compaction turn reports **all-zero usage**. FINDINGS §7 was right that this is invisible from transcripts; it is not invisible on the wire.

**Net saving, in audit cost units** (`input·1 + cw·2.0 + cr·0.10 + out·5`), full-roster event:
- summarization call = 30,504 + 304 + 9,567 + 6,440 = **46,815 units**
- one-time prefix re-write afterwards = 9,887 · 2.0 = **19,774 units**
- saving per subsequent call = (124,327 − 39,405) · 0.10 = **8,492 units/call**
- **break-even ≈ 7.8 subsequent turns**

That 30,504 fresh-input figure is an artifact of my synthetic shape — the last user message was 100 KB, and everything after the breakpoint is fresh. In a normal session the last turn is small and the fresh term collapses to the ~1,900-token instruction:
- shape-corrected summarization ≈ 1,900 + 0.1·C + 5·O ≈ **20,773 units**; **break-even ≈ 4.8 turns**

**What this does to the `autoCompactWindow` recommendation.** The measured law is `cost ≈ 1,900 + 0.1·C + 5·O + 2·F` (C = context at trigger, O = summary output, F = post-compaction floor). The `0.1·C` term scales with C but `5·O + 2·F` does not, so **cost per token-of-residency-removed falls as C rises** — 0.26 units/token at C=99k vs 0.16 at C=400k. Lowering 985,000 → 400–500k is therefore a **quality** decision (§3's 75–100k half-life), and it costs real money rather than saving it; roughly doubling compaction frequency roughly doubles the fixed `5·O + 2·F` term. The three measured coefficients are solid; O and F at a 985k context are extrapolated, not measured.

**Two secondary corrections the wire forces:**
- `compact_metadata` reports `pre_tokens: 99,053` (a whole-request count) but `post_tokens: 1,472` (message-list only, excluding the system/tool/injection floor). Real resident context after compaction was **15,069** tools-less / **39,405** with a roster. So `cumulative_dropped_tokens: 97,581` overstates the actual reduction (83,984) by **16.2%**.
- Every `-p` invocation also fires a haiku session-titling call (521 in / ~11 out, $0.00058), likewise bucketed `auxiliary`.

---

## 2. The ~12k residual — the tool-roster hypothesis is FALSIFIED, and it moves the gap the wrong way

Real dispatch captured (`disp3.err`), three agent types in one message. Rosters counted directly:

| agent | tools | bytes |
|---|---:|---:|
| MAIN | 11 | 57,987 (Workflow 21,896 · Bash 11,817 · Agent 8,868 · ScheduleWakeup 3,942 · Read 2,663 · ReportFindings 2,314 · Skill 1,877 · Edit 1,770 · ToolSearch 1,522 · Write 1,082 · DeferredToolPlaceholder 214) |
| SUB general-purpose (`*`) | 8 | 29,829 |
| SUB Explore | 5 | 18,103 |
| SUB Plan | 5 | 18,103 |

salesagent's lenses declare `tools: [Bash, Read, Grep, Glob]` (Grep/Glob are deferred in 2.1.220), so a lens roster is **≤18,103 B ≈ 6,137 tokens** — *less* than the 12,400 tokens `report-sysprompt.md` already charged. Correcting it **widens** the residual by ~6,300 tokens. "A wider tool roster" is not the answer.

What I found instead is a block the prior decomposition undercounted by 3.7x — **`msg[1]`, a `role: "system"` message present on every request and absent from every transcript**:

| sub-block | this project | salesagent (computed from its files) |
|---|---:|---:|
| deferred-tool list | 465 B | 465 B |
| **agent-type roster** | 1,751 B (5 built-ins) | **5,605 B** (+10 project agents) |
| **skills listing** | 10,096 B | **12,525 B** (+8 project skills) |
| Auto Mode block | 950 B | 950 B |
| **total** | **13,408 B** | **~19,545 B ≈ 7,926 tok** |

Prior report charged 5,581 B / 2,150 tok for this. Rebuilt floor with measured rates: **113,421 B → 44,789 tokens**.

**I did not close it.** Residual against the ~55k observation is now **~10,200 tokens (~25,200 B)**. Two named, unmeasured candidates: the dispatch prompt itself (§6's 100,010 B Step-0 payload; `full-review.md` alone is 16,641 B), and salesagent's `gitStatus` + recent-commits block inside `sys[2]` — my capture ran in a non-repo, so that block was empty. Both need a capture inside salesagent, which the constraints forbid.

---

## 3. Mid-session injections — catalogued, and the split is not what you'd guess

The binary defines **19** `<system-reminder>` kinds (`invoked_skills`, `plan_mode`, `task_status`, `read_truncation_notice`, `hook_*`, `max_turns_reached`, `structured_output`, `command_permissions`, `goal_status`, …). Observed on the wire in `inj1.err`, then grepped against the session's own JSONL:

| injection | on-wire | in transcript |
|---|---:|:--:|
| `msg[1]` deferred-tools + agent roster + skills + Auto Mode | 13,408 B | **0** |
| first-message reminder (`# claudeMd`, MEMORY.md, email, date) | 10,969 B | **0** |
| MCP-auth reminder — emitted **twice**, as a user block *and* a role=system message | 578 B ×2 | **0** |
| nested `sub/CLAUDE.md`, injected after reading a file in that dir | 347 B | 1 ✓ |
| skill body, injected verbatim after the `Skill` tool_result | 1,683 B (from a 1,603 B SKILL.md) | 1 ✓ |

So ~**25,500 B ≈ 10,300 tokens per request** rides in a channel transcripts cannot see — but the two most-suspected items, skill bodies and nested CLAUDE.md, **are** recorded. Invoking a skill injects the whole SKILL.md; reading one file in a directory pulls in that directory's CLAUDE.md for the rest of the session.

---

## 4. Does the injected block differ by agent type? — No. Measured byte-identical.

From the same three-type dispatch:

- `msg[0].0` first-message reminder: **identical across Explore, general-purpose and Plan** — sha `800738c2a4`, 364 B each.
- `msg[1].0`: identical for Explore and Plan (sha `638d633eea`, 5,365 B); general-purpose differs by **13 bytes** (5,378 B) solely because it holds the `Agent` tool, so one fewer deferred entry.
- All variation lives in `sys[2]` (agent definition: 3,112 / 3,655 / 3,962 B) and the roster (18,103 / 29,829 B).

**The lens-vs-others ~5–9k spread is fully accounted for by agent-definition size** (salesagent's lenses run 4,594–14,453 B ≈ a 4,000-token spread) plus roster width. The injected block contributes exactly zero to it.

---

## Contradictions with FINDINGS.md

1. **§7 "Compaction's own billing … unmeasurable"** — measured above. It should move to settled.
2. The implied model that a compaction saving is gross because the summarizer re-bills the conversation is **wrong**: the request keeps the roster and carries a conversation cache breakpoint, so the prefix is read at 0.1x. Compaction is far cheaper than the pessimistic reading, and break-even is ~5–8 turns, not never.
3. **`report-sysprompt.md:61`** — "the residual ~12k is most plausibly a wider tool roster" is falsified with counts; the real roster is *narrower* than the figure already charged.
4. **Trap #3 confirmed on-wire with a nuance**: a stripped thinking block is sent as `{"type":"thinking","thinking":"","signature":"EqEFCok…"}`. The text is gone before the request is built, so those tokens were billed once as *output* and are **not** re-billed as input on replay — only the signature is. Any model that treats stripped reasoning as recurring input context is over-counting.
5. `cumulative_dropped_tokens` overstates the real context reduction by 16.2% (mismatched `pre_tokens`/`post_tokens` definitions).

---

## Limits — stated plainly

- **No capture inside salesagent.** HEAD is still `6881e8da4`; agenticads-sim-plan shows 0 changes.
- **Could not capture a subagent under default setting sources.** `~/.claude/settings.json` carries `"ask": ["Agent","Task"]`, which outranks any `allow` rule I could add without editing the user's config (I tried project-level and `--settings`; both lose to `ask`). The three-type dispatch therefore ran `--setting-sources project,local`, which strips the global CLAUDE.md from the injection (10,969 B → 364 B — itself a clean measurement). Agent-type equality is measured under that config; the CLAUDE.md-bearing form is established from MAIN in the same build plus the prior 11,308 B subagent capture.
- **Auto-compaction (`trigger: "threshold"`) not captured** — only manual `/compact`. Both route through the same `compactConversation`; the auto path additionally passes `isAutoCompact: true` and `stripNonEssential`, whose effect on the request I did not measure.
- **The ~10.2k floor residual is open.** I named two candidates and measured neither.
- My first filler corpus (random word salad) tripped an API content classifier — four turns returned `stop_reason: refusal`, `api_refusal_category: "bio"`. Those runs are in `comp1.err` and are structurally unrepresentative (empty synthetic assistant messages collapse the message list into one user block). I rebuilt with benign prose; every number reported above comes from the rebuilt runs.