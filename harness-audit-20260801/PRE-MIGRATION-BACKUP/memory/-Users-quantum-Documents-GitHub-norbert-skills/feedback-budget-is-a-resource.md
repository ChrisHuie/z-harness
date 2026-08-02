---
name: feedback-budget-is-a-resource
description: "Subscription token budget is a metered, window-expiring resource — match spend to value; ceremony proportional to stakes; token-maxxing only on expiring surplus or genuine need; state cost before any fan-out"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 7b516ca9-eebb-4001-862f-a803cd7034ba
---

<!-- audit-2026-08-01 -->
> **SUPERSEDED as of 2026-08-01.** Duplicates `/Users/quantum/.claude/projects/-Users-quantum-Documents-ComputedChaos-salesagent/memory/feedback_no_agent_fanout_by_default.md`, which is kept as the canonical version. Kept for history.
> Rationale: The operative rule (count cost before spawning; ceremony proportional to stakes) is already stated by a HIGH-trust twin AND already promoted into ~/.claude/CLAUDE.md's fan-out section.


The user's session/weekly window reset with unused budget while I was
spinning up a contract + subagents to answer a question ABOUT resource
efficiency. His correction: "you missed this critical reality of
agentic development... effort, cost, using subscription budget as a
resource, utilizing resources more efficiently and just not token
maxxing unless it doesn't matter or it is needed. You don't get this
and it keeps costing us actual money."

**Why:** Claude plan limits are expiring windows (5-hour session +
weekly caps), so token value is TIME-VARYING: scarce mid-window, worth
~zero at reset. He pays real money; waste = mismatch in both
directions — heavy apparatus on light questions mid-window, AND surplus
dying at reset while pre-approved heavy work sits parked. Family
lineage: hc06 (silent tier downgrade), hc07 (tier provenance), now
hc08/T12 (ceremony-maxxing / resource-blindness) — all
resource-decisions-made-silently.

**How to apply:** (1) Before ANY fan-out/workflow: state estimated cost
and window position, get the go unless pre-authorized — surfacing is
the rule, not frugality per se. (2) Default inline; delegate only when
independence/parallelism genuinely buys something. (3) Ceremony
proportional to stakes — the mint-predicate logic applies to RESOURCES,
not just records: light questions get direct answers, not
contract+workflow+episode apparatus. (4) Near window reset with
surplus: that is when maxxing is rational — drain the parked
pre-approved queue (scenarios, sweeps, distillations), never invent
work. (5) Answer from knowledge first when confidence is high and mark
uncertainty, instead of reflexively researching. Related:
[[feedback-no-self-declared-convergence]],
[[feedback-timeout-is-not-an-answer]].
