Read all three documents in full, then measured rather than accepted. Findings below; every number is from a script I ran over the 691 MB transcript corpus.

---

# The plan's ranking is inverted, and its #1 item rests on a premise that is false in this harness

**Measured corpus decomposition** (1,148.5M cost units, dedup by `requestId`, `input×1 + cache_wr×1.25 + cache_rd×0.10 + out×5`):

| line item | Munits | % |
|---|---|---|
| subagent later-call cache_read | 426.4 | 37.1% |
| main later-call cache_read | 268.3 | 23.4% |
| subagent later-call cache_write | 140.0 | 12.2% |
| **main output (mostly reasoning)** | **129.0** | **11.2%** |
| main later-call cache_write | 96.3 | 8.4% |
| **subagent first-call cache_write (static floor)** | **56.4** | **4.9%** |
| subagent output | 16.5 | 1.4% |

Cache read is 60.5% of cost and it is a **pure multiplier on residency**. The correct metric is not tokens — it is **token-turns**. The plan ranks by tokens, which is why it is ordered wrong.

Measured residency: **37.3 API calls per subagent dispatch** (median 31, p90 67, max 179); charter enters at call index 0 and sits in context for a **median of 34 further billed calls**. Main sessions: 61.6 calls, mean context 283k/call.

---

## 1. Does #1 actually work? No. 0 of 859.

The plan assumes system-prompt content is cache-cheap. I measured every subagent dispatch's first call:

```
first-call cache_WRITE  median 53,201   total 45.1M
first-call cache_READ   median  1,915   total  1.7M
dispatches whose first call hit the prefix cache (>20k read): 0 / 859 = 0.0%
```

**The subagent system prompt is cache-*written* fresh on every single dispatch.** Moving the charter from a tool_result into the system prompt moves 13.4k tokens from cache_write@1.25 to cache_write@1.25. The residency tail (34 further turns @0.10) is identical in both placements — a system prompt is re-sent every turn exactly like a message.

Net delta is **only the two removed Read round-trips**: 2 × ~60k context @0.10 ≈ 12-14k units/dispatch. Repriced: **7.2-8.4M units = 0.63-0.73% of corpus**, not "the single largest win."

Two further corrections to its baseline:
- The 738-dispatch figure is wrong. Measured lens dispatches: **756**, of which only **598 load the charter by any route** (below). Baseline is ~36% over-stated.
- Charter cost is **62.4k units/dispatch** (16.75k write + 45.6k residency). Fix #1 captures the 0% portion. The 73% that is residency tail is untouched by relocation and only removable by **deletion**.

**Compliance evidence points the opposite way from the plan's argument.** `~/.claude/CLAUDE.md:56-57` — "citing filenames does not make a subagent read them" — and `review-charter.md:13` — "Citing a filename is not reading it" — are two independently-recorded lessons that a subagent's attention follows the *act of reading*, not passive presence. Relocating to the system prompt is the passive form. There is no corpus evidence either way on system-prompt compliance; **the plan should not assume parity, and no one has tested it.**

## 2. The metric is wrong, and it hides a live quality defect

I checked whether agents actually execute Step 0:

| lens | dispatches | Read charter | rate |
|---|---|---|---|
| architecture-guards | 118 | 77 | 65% |
| admin-ui | 19 | 12 | 63% |
| spec-conformance | 112 | 75 | 67% |
| bdd | 87 | 60 | 69% |
| test-integrity | 126 | 91 | 72% |
| security | 85 | 64 | 75% |
| error-wire | 90 | 70 | 78% |
| code-patterns | 119 | 95 | 80% |
| **TOTAL** | **756** | **544** | **72%** |

Allowing for `cat`/relative-path/inlined routes: **79% load it. 158 of 756 lens dispatches (21%) never load the charter by any detected route** — despite every agent def stating "Step 0 — MANDATORY: read these FIRST."

One fifth of the review panel runs with no evidence rule (§1.1), no masking-gotcha doctrine (§2), no disposition format (§3). That is a defect in the load-bearing harness, sitting in plain sight in the same measurement the optimization work was doing, and nobody named it.

**This inverts fix #1's justification.** System-prompt placement would make the charter unconditionally present in 100% of dispatches. That is a real argument for it — worth more than the token math — and the plan does not make it. **#1 is right for a reason it does not state, and wrong for the reason it does.**

## 3. Fix #2's compression is arithmetically impossible as described

The plan's own two facts contradict each other. FACTS.md:53: payload is "22-37% actual prose; 33-47% JSON envelope." FACTS.md:50-51: `--index` renders 26,409 → 1,296 tok.

- PR 1616: prose alone = 5,810-9,771 tok. Index output = 1,296 tok = **13-22% of the prose.**
- PR 1720: prose alone = 19,083-32,095 tok. Index = 3,868 = **12-20% of the prose.**

`--index` is not envelope-stripping. It is **discarding 78-88% of actual reviewer prose.** The plan describes it as "render already-fetched review state compactly," which reads as lossless. It is not.

**The specific defect class this lets through**, named in Chris's own charter:
- **§1.7b (`review-charter.md:28`)** — "an inherited item is a claim, not a fact... Verify each one's **premise**." The miss it exists for: a colleague's ask was unsatisfiable because `issubclass(TaskNotFoundError, AdCPError)` is `False`. **You cannot recover a premise from an index row of `path:line @author date`.** The premise lives in the discarded prose. Cost of that miss, per the charter: "we carried it into the ledger for a full round."
- **§7d (`:30`)** — "when a specialist reports 'X happens **because** Y', the X is evidence and the Y is a hypothesis." The because-Y is prose. An index has no because.
- **§4c.1 (`:126`)** — "Read a nonzero exit as a per-thread worklist." A worklist of *paths* is not a worklist of *asks*.

Note the current script already caps at 12 (`review_completeness.py:178`, `for t in group[:12]`) — so compression is not new. But 12-with-full-bodies and 118-as-index are different failure modes: the first drops threads visibly, the second drops reasoning invisibly across all of them.

**This is the plan's biggest real win and its most dangerous change simultaneously.**

## 4. Fix #3 is the correct mechanism but factually mis-scoped

FACTS.md:41-43 asserts §4b and §4c are "both orchestrator-only... sent to 738 lens agents that structurally cannot act on them." **That is false for §4c.** Read the six preconditions:

- §4c.1, §4c.6 — orchestrator. Correct to move.
- **§4c.2 (`:128`)** — the serializer-tautology trap: "a BDD wire-oracle step that reads `ctx.get("wire_response")` inline with a `model_dump()` fallback." That is a `review-bdd` defect class.
- **§4c.3 (`:129`)** — written in the second person *to the raising agent*: "**if YOU raised** 'step X passes vacuously,' **you own** finding the same shape in `TestX...EveryTransport`."
- **§4c.4 (`:130`)** — hand-DRY-sweeping new test code. `review-test-integrity`'s job.
- **§4c.5 (`:131`)** — partial-copy set/frozenset literals. `review-code-patterns`' job.

Splitting "§4b/§4c" wholesale strips four agent-facing techniques, one of which is addressed directly to the agent. §4b alone is genuinely orchestrator-only. Repriced correctly (2,936 tok × [1.25 + 34×0.10] × 598) = **8.2M units = 0.71%** — roughly equal to #1, achieved by the right mechanism (removal, 73% of it residency), and it must be §4b **plus §4c.1/.6 only**.

## 5. Fix #4 is correct, with one named exception

`--log-failed` being byte-identical to `--log` was verified with `cmp`; anchor-windowing CI logs discards timestamps and unrelated lines, which carry no premises to falsify. Repriced: 21.9k × 3.75 × ~100 = **8.2M units = 0.71%**. Low risk. Ship it.

The exception: **`review-charter.md:53` (masking-gotcha #10)** documents a failure where `tests/unit/test_scheduler_env_var_handling.py` pollutes via `importlib.reload` and a *different, later* test fails — "intermittent under default randomisation (3 of 5 runs), so it reads as flakiness," and "two reviewers independently burned a round on this." An anchor window centred on the failing test **hides the polluter**. The window must include the pytest random-seed/order header and the complete failure list, not just the anchor region.

## 6. Fix #5 converts a live check into a stale claim

`~/.claude/CLAUDE.md:41` — "**Preflight EVERY dispatch** — before, not after the first odd report." Lines 48-49: "At 100% disk every command fails `ENOSPC` on unrelated paths and **mutation agents emit false findings**. Infra failure is neither pass nor fail."

Emitting preflight state as JSON *once per fan-out* means agents at turn 60 of a 67-turn dispatch are reading a disk/Docker snapshot taken 30+ minutes earlier. Disk filling *during* a fan-out is precisely the documented failure mode. A once-per-fan-out snapshot makes agents trust a stale "disk OK" and produce exactly the false findings CLAUDE.md warns about. It saves the least and is the only item that contradicts an explicit rule. **Drop it, or make agents re-check on any anomalous result.**

## 7. Three cost drivers nobody looked at — each larger than four of the five plan items

**A. The subagent static floor never caches: 4.9% of corpus, ceiling 4.5% recoverable.** 45.1M tokens of cache_write, **0/859 prefix hits**. Eight different agent `.md` bodies dispatched minutes apart against a 5-minute TTL. Placing an *identical* block at the very top of all 8 bodies would let concurrent fan-out members share a prefix (1 write + 7 reads) — which is the only configuration in which fix #1 pays. The plan does not specify placement, so as written it gets zero.

**B. Reasoning residency: 12.6-14.2% of corpus, and FACTS.md:27 is confirmed.** I regressed context growth on prior output across 9,579 main-thread turn pairs:

```
delta_context = 1.012 × prev_output_tokens + 1,633
```

Coefficient 1.0 — **reasoning persists at full weight.** Decomposed:

```
MAIN     : growth = 0.959×prev_output + 1,934  =>  output 57% of growth, tool results 43%
SUBAGENT : growth = -1.232×prev_output + 3,419 =>  output ~0%,            tool results ~100%
```

So the plan's tool-result focus is **correct for subagents** (77% of calls, 56% of cost) and **addresses the smaller half on main**, where the model's own output is 57% of context growth. Every main output token is billed twice: 5× as output, then 0.10× per remaining turn — 129M + ~64M tail = **16.9% of corpus**, reasoning's share 12.6-14.2%.

Cutting reasoning *depth* is the hidden downgrade and is correctly out of scope. **Cutting the reasoning *tail* is not.** Turn-3 thinking is re-billed 30 more times and is not load-bearing at turn 40. Dropping thinking blocks older than N turns from the resent context would recover ~5.6% with **zero loss of reasoning depth** — the model still thinks as hard, it just stops re-reading its own scratchpad. Whether this harness exposes that control I could not determine; it is the largest quality-neutral lever available and nobody named it.

**C. Turn-count superlinearity: top 10% of dispatches = 14.5% of corpus.**

```
top  5% of dispatches ( 42, mean 104 turns) = 15.8% of subagent cost
top 10% of dispatches ( 85, mean  88 turns) = 26.0%
top 20% of dispatches (171, mean  72 turns) = 41.4%
median dispatch: 0.60M units, 30 turns   |   most expensive: 5.08M units, 177 turns
```

FACTS.md:58 says "**No single whale.**" That is true of *content items* and false of *dispatches*: one dispatch is 5.08M units = **0.44% of the entire corpus**, and 42 dispatches carry 15.8% of subagent cost. All five plan items are content fixes; none touches dispatch shape.

Cost per dispatch ≈ `n×floor + growth×n²/2`. At floor 53k and growth 3.35k: n=177 → 62.0M tok; three dispatches of n=59 → 26.9M tok. **Same 177 turns of work, 57% cheaper** — if it partitions, which late-dependent work often does not.

## 8. The 8-lens architecture: the charter itself is the indictment

Nobody questioned the shape. The charter documents three named misses **caused by the dimension split**:

- **§5b (`:23`)** — "the structural reason we missed it is that **reviewers are dispatched by DIMENSION**, so a defect living on the seam between two (error-wire saw a bad `except`; code-patterns owns DRY but was not looking at the auth preamble) is **owned by neither**."
- **§5d (`:25`)** — "Same line, two dimensions, and we only read it in one."
- **§4b.0 (`:108`)** — "two agents each raised one shard of [one finding] as a separate NIT; unsynthesized, **both were dropped**."

The response to each was **more charter prose shipped to every agent**. §5b+§5c+§5d+§4b.0 alone are ~1,900 tokens of seam-compensation text, paid 598× — the architecture's defect converted into a recurring token bill. **The charter is large substantially because the shape is wrong.**

Cost by lens is near-flat (9.8%-16.1%), so there is no cheap lens to cut and dropping one is a 1/8 quality cut Chris's rules forbid. But flatness also means cost tracks **turns, not lens identity**. The whales are `test-integrity` (4 of top 8), `bdd` (2), `error-wire` (2) — the lenses that *run* things, per §1.3 "empirical over static... comes from RUNNING." **The expensive dispatches are expensive because they are doing the thing that makes the review real.** That is the honest answer to "would 4 deeper agents beat 8": untested, but the charter's own evidence says seam defects are structurally invisible to 8 narrow lenses, and 4 broader ones would see them. Nobody has run that experiment. It is the highest-value experiment available and it is not in the plan.

## 9. Sequencing: you cannot currently prove any of this worked

**No fix has a stated before-measurement, and dispatch cost variance is 8.5× (0.60M median → 5.08M max).** Fix #1 and #3 each move ~10% of a dispatch's cost. **A 10% effect is undetectable against 8.5× variance without pairing.** Anything shipped without a paired A/B (same PR, same lens, same round) will produce an unfalsifiable "it seems better."

Order:
1. **First, fix the 21% charter non-load.** It is a live quality defect and it changes fix #1's entire justification. Optimizing delivery of a document a fifth of dispatches never load is optimizing the wrong thing.
2. **Then #4 (`ci_failure.py`)** — smallest blast radius, no reviewer prose at risk, plus the seed/failure-list caveat.
3. **Then #3, scoped to §4b + §4c.1/.6 only.**
4. **Then #2 at a much lower compression** (see below).
5. **Never #5 as specified.**

**Irreversible / hardest to undo:** duplicating a 40 KB charter into 8 agent files that `review-charter.md:96` confirms are **gitignored** (`.gitignore` covers `.claude/agents/review-*.md`). Eight untracked copies, no diff review, no history, no test — and drift is undetectable. Charter §5b: "**COUNT THE COPIES BEFORE PROPOSING THE FIX... If N > 1 the finding is 'this operation has no home,' and the fix is the seam, not the site.**" Fix #1 as written commits the exact defect class §5b exists to catch, in the file that defines §5b. If the charter goes into agent prompts, it must be **generated from the single source at dispatch time**, never hand-copied.

---

# Closers

**Weakest claim: that moving the charter into system prompts saves ~10M tokens.** Measured: **0 of 859 dispatches get a prefix cache hit**; median first-call `cache_write` 53,201 vs `cache_read` 1,915. Both placements are cache_write@1.25 followed by identical residency. The real saving is two removed round-trips — **0.63-0.73%, not the largest win** — and the baseline is 36% over-stated because only 598 of 756 dispatches load it at all. Repriced, the ranking becomes **#2 (3.3-9.4%) ≫ #4 ≈ #3 ≈ #1 (~0.7% each) > #5 (negative)**. Item #2 is worth more than the other four combined, several times over.

**Most dangerous change: `review_completeness.py --index` at 95%.** By the plan's own numbers it discards 78-88% of *reviewer prose*, not envelope. It sits directly on the readiness gate, runs 306-533 times, and destroys the input to charter §1.7b ("verify each inherited item's **premise**") and §7d ("the because-Y is a hypothesis") — the two rules written for misses that each cost a full round. **Build it, but target ~60-70% (envelope + duplicated hunks only), keep every comment body verbatim, and make the compression ratio a printed field so a silent drift toward 95% is visible.** Runner-up: fix #5, the only item that contradicts an explicit CLAUDE.md rule.

**The one thing I would add: a per-dispatch cost/turn budget with split-not-truncate, backed by the accounting instrument.** The top 10% of dispatches (85 runs, mean 88 turns) carry 26% of subagent cost = 14.5% of the corpus, and cost grows as `n×floor + growth×n²/2` — so splitting a 177-turn dispatch into three 59-turn ones is **57% cheaper for identical work**. That is 20× fix #1, it is quality-neutral (no lens dropped, no evidence discarded), and it is invisible to a plan that ranks by tokens. Its prerequisite is the same instrument that would let you prove fixes #1-#4 worked at all: per-dispatch cost units by lens and round, captured **before** any change lands.

---

**What I did not test:** the 533-invocation count for `review_completeness.py` (I measured 306 transcript *files* containing the string — files ≠ invocations, so my #2 pricing is a 306-533 range); whether a shared top-of-body block would actually cache-hit across a concurrent fan-out (I measured only that today's configuration hits 0/859); whether an agent complies with a system-prompt charter as reliably as one it Read — no corpus evidence exists either way, and this is the assumption fix #1 most needs; whether this harness can drop stale thinking blocks; the inherited 3.8 chars/token calibration; and fix #5, which I did not price. My charter-load detection matched `file_path` tool_use plus `cat`/relative/inlined-body routes — a route I did not model would lower the 21% non-load figure, so verify it before acting on it.

Scripts are at `/private/tmp/claude-501/-Users-quantum-Documents-GitHub-agenticads-sim-plan/e2367c8b-0c8b-43ae-a5d4-98ce3fbcecea/scratchpad/` (`turns.py`, `cache.py`, `main.py`, `charter.py`, `floor.py`, `reason.py`, `decomp.py`, `conc.py`, `who.py`, `comply.py`, `comply2.py`).