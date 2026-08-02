---
name: reference_claude_code_measurement_traps
description: "Four traps that make any naive measurement of Claude Code token cost wrong — verified universal across 12 projects / 187 dirs. Dedupe by requestId, UNION content blocks, take MAX output_tokens, use the nested subagent path."
metadata: 
  node_type: memory
  type: reference
  originSessionId: e2367c8b-0c8b-43ae-a5d4-98ce3fbcecea
  modified: 2026-08-02T03:31:51.548Z
---

Measured 2026-08-01 across 63,290 API calls in 12 projects (187 dirs scanned). Full audit:
`~/.claude/harness-audit-20260801/`.

**Trap 1 — one API call writes MULTIPLE JSONL records**, one per content block (thinking,
text, each tool_use), and every record carries a COPY of the same `usage`. Naive summing
inflates ~3x (2.34–3.64x across projects, median 3.00). **Dedupe by `requestId`.**

**Trap 2 — subagent transcripts are at `<session-id>/subagents/agent-*.jsonl`**, one level
DOWN. `<project>/subagents/*.jsonl` returned **0 files in all 187 directories**. Missing them
silently drops **56–85% of all calls** and 32–79% of cost.

**Trap 3 — `thinking` blocks may persist as `""`** (text stripped, tokens billed and still
resident in context). Version- and project-dependent, not a format guarantee. Derive as
`output_tokens - visible/chars_per_token` when they are empty.

**Trap 4 — records sharing a `requestId` carry DIFFERENT `output_tokens`**: provisional on
the first content block, final on the last. Keeping the first — which is what dedupe naturally
does — **undercounts subagent output by 90.8%**. Main threads are unaffected (0.0% in every
project). **Take `max(output_tokens)` per `requestId`.**

Correct pipeline: drop repeat `uuid` (session-resume replay) → group by `requestId` →
**union content blocks** → take max `output_tokens` → drop `model == "<synthetic>"`.

**Pricing:** cache TTL differs by thread type, universally and without exception — main
thread 100% `ephemeral_1h` (bills **2.0x**), subagents 100% `ephemeral_5m` (**1.25x**). Using
1.25x everywhere understates ~20%. Cache read 0.10x, output 5x.

**chars/token is not a scalar** — `tokens = content + framing`, so the ratio rises with call
size (1.40 smallest quintile → 2.47 largest). Fitted: text **2.67**, tool JSON **2.53**, plus
69.7 tok per `tool_use` and 17.3 per call (n=820, R²=0.9964). Independently cross-checked
from the input side at 2.48. A commonly assumed 3.80 is wrong and inflates any derived
"reasoning share".

Related: [[feedback_verify_with_the_same_instrument]]
