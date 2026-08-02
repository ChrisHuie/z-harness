# Established facts — do NOT re-derive. Challenge if you find contrary evidence.

Corpus: Chris's salesagent Claude sessions. Repo `/Users/quantum/Documents/ComputedChaos/salesagent`,
canonical remote `prebid/salesagent` (note: `affinity-com/salesagent` is a FORK; older memories
wrongly cite it). Transcripts: `/Users/quantum/.claude/projects/-Users-quantum-Documents-ComputedChaos-salesagent/`

## Corrected corpus measurement (measure2.py, dedup by requestId, includes subagents)

```
              calls    input  cache_wr  cache_rd   output  cost units
main          9,799     2.3M     85.6M     2.69B    25.8M      506.8M
subagent     32,060     2.4M    157.1M     4.27B     3.3M      641.8M
TOTAL        41,859     4.6M    242.7M     6.95B    29.1M       1.15B
```
- **Subagents: 77% of API calls, 56% of cost.**
- Re-read multiplier (cache_read / cache_write): **28.7x**
- Billed share: **cache read 60.5%**, cache write 26.4%, output 12.6%, fresh input 0.4%
- Cost units = `input*1 + cache_write*1.25 + cache_read*0.10 + output*5`

### Three measurement traps — I fell into all three. Do not repeat them.
1. **One API call writes MULTIPLE JSONL records** (one per content block: thinking, text, each
   tool_use), each carrying a COPY of the same `usage`. Naive counting inflates ~2.9x.
   **Always dedup by `requestId`.**
2. **Subagent transcripts are at `<session-id>/subagents/agent-*.jsonl`** — one level DOWN, not
   `<project>/subagents/`. 859 files, 429 MB. A top-level glob silently misses 77% of all calls.
3. **`thinking` blocks persist as `"thinking": ""`** with a ~3KB signature — text is stripped.
   Reasoning tokens were paid and remain in context but are INVISIBLE in the transcript.
   Derive as `output_tokens - visible_output_chars/3.8`. Reasoning ≈ 75-84% of main-thread output.

## Findings from pass 1 (verified by the orchestrator unless marked)

- **7,475 Bash calls; 5,945 (80%) are git/GitHub state queries.** 7,344 unique command strings —
  almost no exact repetition, so caching is useless; repetition is in INTENT. 6,022 of 7,344 are
  compound (`&&`/multiline) — the model hand-assembles a composite state report each time.
- **851 Agent dispatches; 738 (86.7%) are one fixed 8-lens review panel** re-run per PR per round.
  Lenses: architecture-guards, test-integrity, code-patterns, spec-conformance, error-wire,
  security, bdd, admin-ui — each backed by `.claude/agents/review-*.md`.
- **Every lens agent must Step-0 read `review-charter.md` (39,867 B) + `reviewer-tooling.md`
  (13,627 B)** = 53,494 B ≈ 13.4k tokens x 738 dispatches ≈ **~10M tokens of unchanged text.**
  VERIFIED: all 8 agent defs reference both; header reads "Step 0 — MANDATORY: read these FIRST".
  - Charter §4b (line 104) is labelled "(orchestrator — before ANY public-facing artifact)" and
    §4c is the readiness-verdict gate — both orchestrator-only, ~2,936 tok, sent to 738 lens
    agents that structurally cannot act on them.
  - Charter §5 is a mandatory-read list INSIDE the file read because of that list (~207 tok).
- **In PR #1417 alone, `review-charter.md` was read by 53 DIFFERENT agents** (149.5k tokens);
  `reviewer-tooling` by 47; individual memory files by 42, 41, and 31 agents respectively.
- **`review_completeness.py` fetches all 4 review surfaces then DISCARDS the bodies** — prints only
  counts/paths capped at 12 plus a verdict. VERIFIED at
  `.claude/rules/private/detectors/review_completeness.py:112-128`. So the model re-pulls the same
  4 endpoints by hand to read the feedback. Measured `--index` prototype: 26,409→1,296 tok (95.1%)
  on PR 1616; 86,742→3,868 (95.5%) on PR 1720. Zero extra network calls.
  - PR 1720's 3 REST endpoints un-`jq`'d = 222,872 tokens (larger than a context window).
  - Payload is 22-37% actual prose; 33-47% JSON envelope; up to 50% of hunk bytes duplicated.
  - GraphQL↔REST join verified exact: 118/118 by `databaseId`.
- **`gh run view --job N --log-failed` returns BYTE-IDENTICAL output to `--log`** (90,229 B both,
  `cmp` identical). GitHub's own reduction flag is a no-op here. Anchor-windowing + stripping the
  per-line timestamp prefix (47.9% of bytes): 22,386 → 507 tok (97.7%).
- **No single whale.** Largest individual context item in any studied session: 9.5k tokens. Cost is
  a long tail of 2-7k items each re-read 90-290x. File reads/diffs are only 3-7% each.
- **20-50% of tool results are redundant re-fetches** (PR #1417: 1,965k of 3,960k tokens).
- **5 of 8 salesagent skills cannot execute Step 1**: `audit`, `guard`, `integrate`, `surface`,
  `verify-spec` all call `.claude/scripts/cook_formula.py` (ABSENT) and/or `bd` (NOT INSTALLED).
  `verify-spec` hardcodes `/Users/konst/projects/adcp` — a collaborator's home dir, nonexistent here.
  Two agent defs (`review-architecture-guards`, `review-spec-conformance`) contain instructions to
  "strip the beads/cook_formula layer" / "IGNORE those" — a workaround layer paid in context.
- **12 working detectors exist** at `.claude/rules/private/detectors/` (3,422 lines Python).
- **Static per-call floor ≈ 77-85k tokens** (system prompt + tools + CLAUDE.md + skills); subagents
  start at ~46-50k. Fitted, RMS error 3-6k. (Sample of 4 sessions — treat as provisional.)
- **Largest single item found**: the `update-config` skill body injected as a user prompt in
  PR #1247 — 39.4k tokens re-read 110 times = 4.34M tokens. Mechanism NOT yet explained.
- salesagent also has `tests/CLAUDE.md` (443 lines) auto-loaded under `tests/`, on top of the
  750-line root `CLAUDE.md`.

## Known coverage gaps in pass 1 — these are why you exist

- Per-session attribution came from **6 sessions of 159**. Corpus totals are complete; the
  BREAKDOWN is a sample.
- The 3.8 chars/token calibration carries 3-6k RMS error.
- All three pass-1 agents were told what to look for. **Absence of an unlooked-for cost driver is
  not evidence it does not exist.**
- Never investigated: whether the 12 detectors are actually INVOKED; compaction frequency/cost
  (`autoCompactWindow` is 985000); the 10 `.claude/agents/review-*.md` definitions themselves;
  cross-session (not just in-session) redundancy; why a skill body became a user prompt; whether
  reasoning-token volume is reducible; the composition of the 80k static floor.

## Standing constraints

- Chris's review harness is LOAD-BEARING. Cutting review capability to save tokens is the
  "hidden downgrade" his own rules name as the cardinal sin. Cheaper agents, not fewer lenses.
- READ-ONLY. Analysis only. A harness hook blocks subagent file writes — **return findings as your
  final message text**, never a file.
- Ground every claim in something you ran or read. Cite `path:line` or the command.
- Say what you could NOT measure rather than estimating silently.
