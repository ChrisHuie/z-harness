---
name: Opus subagent verification for comprehensive plans
description: For high-stakes planning work, user directs explicit use of Opus subagents with max thinking; in practice this catches dozens of findings single-pass planning misses.
type: feedback
originSessionId: b20ae879-7b4d-4db0-b610-d3da63c2f4da
---

<!-- audit-2026-08-01 -->
> **STALE as of 2026-08-01.** Verified no longer accurate during the memory-consolidation audit. Kept for history; do not act on it.
> Evidence: Contradicted from two directions. (1) HIGH-trust feedback_no_agent_fanout_by_default.md sets the opposite default — 'Default posture for reviews and tasks is a SINGLE PASS done myself with zero spawne

When the user wants a "most comprehensive" plan or asks to "verify as we go
through agents and other means," spawn Opus subagents in parallel for
verification. The pattern that worked during the agentic-advertising bootstrap:

**Three parallel Opus agents covering different angles:**
1. **Critic agent** (subagent_type: Plan, model: opus) — challenges the plan
   end-to-end, finds gaps, proposes specific additions categorized by
   severity (MUST-FIX / SHOULD-FIX / NICE-TO-HAVE).
2. **Source verifier** (subagent_type: Explore, model: opus) — pulls current
   state of every cited upstream source (PyPI, npm, GitHub), corrects stale
   version anchors, surfaces breaking changes the plan missed.
3. **Completeness checker** (subagent_type: Explore, model: opus) — reads
   every source file the plan claims to distill from; identifies concepts
   that were lost or thinned during adaptation.

**Why:** Verified during agentic-advertising bootstrap (2026-05-10). One
verification pass with these three agents found:
- Critic: 5 MUST-FIX gaps (atom-id lifecycle, cross-ref enforcement, schema
  invariants, citation typing, citation rot)
- Verifier: ~14 factual corrections (spec was 3.0.9 not 3.0.6, every overlay
  path in the sample atom was wrong against actual salesagent layout, Python
  SDK 5.0.0 confirmed real, salesagent's `adcp>=3.12.0` pin is unsatisfiable)
- Completeness: 22 gaps including 6 critical concept losses (bottom-left
  quadrant warning, three-question diagnostic, 5-bullet discipline restated)

Without this pass, the plan would have shipped with an unrunnable sample atom
(bad paths) and stale version anchors. Total ~35 substantive findings.

**How to apply:**
- Use `model: "opus"` parameter on Agent calls when the work is high-stakes.
- Spawn agents in parallel (multiple Agent tool calls in one message), not
  serially — they need to start with the same context.
- Each agent's prompt must be self-contained and rich (file paths, what to
  look for, output format spec, word limit). Subagents start cold.
- Synthesize findings yourself; don't just pass them through. The user wants
  proof you understood, not "based on the agents' findings, do X."
- Update the plan file after synthesis; re-attempt ExitPlanMode.
