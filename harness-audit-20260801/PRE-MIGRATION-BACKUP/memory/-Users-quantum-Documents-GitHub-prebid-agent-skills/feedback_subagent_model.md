---
name: subagent-model-and-effort
description: On this project, always use opus model for Agent subagent calls and default to max-effort reasoning. User explicitly requested "Use max thinking and opus subagents everywhere possible".
type: feedback
originSessionId: a5f0807e-b696-4762-a9d9-6f3975c50d85
---

<!-- audit-2026-08-01 -->
> **STALE as of 2026-08-01.** Verified no longer accurate during the memory-consolidation audit. Kept for history; do not act on it.
> Evidence: salesagent/feedback_subagent_model_inherit.md (2026-06-11, renamed from feedback_subagent_model_opus) says verbatim: 'This reverses an earlier always-opus rule' and 'The local review-* agents and full

Use `model: "opus"` on every Agent tool call (Explore, Plan, general-purpose, claude-code-guide). Default to deep/ultrathink-level reasoning on this project's tasks.

**Why:** User explicitly stated "Use max thinking and opus subagents everywhere possible" while approving a multi-phase plan to refresh review skills against 89 reference PRs. The work is high-stakes (skills are in active use) and benefits from the strongest reasoning model.

**How to apply:** When invoking Agent for any subagent_type, pass `model: "opus"` unless the task is genuinely trivial (e.g., a one-shot file read agents won't need). For own reasoning, default to deep analysis. Skip opus override only if a task is small, clearly bounded, and would be overkill.
