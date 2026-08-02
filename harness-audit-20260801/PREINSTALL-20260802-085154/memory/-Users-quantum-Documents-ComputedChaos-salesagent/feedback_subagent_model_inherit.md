---
name: feedback-subagent-model-inherit
description: "Never pin a model class on subagents (no model:'opus'/'sonnet'/...) — omit the param so they inherit the session model the user picked, which IS the latest/best by definition."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: eea6a61f-fb14-405a-8a08-b5c73900ce1c
---

(Renamed from feedback_subagent_model_opus, 2026-06-11 — the old name itself aged, proving the rule.)

When dispatching subagents via the Agent tool, **omit the `model` parameter** so they inherit the session model the user selected. Do NOT pin a specific class like `model: "opus"`.

**Why:** Pinning a class ages badly — any model name is shorthand for "the best one today" and is wrong the moment the lineup changes (proved by the Opus→Fable transition, 2026-06). The user's principle (2026-06-10): "always use any specific model is poor design. Just say latest model instead of a specific class." The Agent tool's `model` enum has no `latest` value, so the faithful way to express "use the latest/best" is to omit the param and inherit whatever the user set the session to — by definition the model they chose.

This reverses an earlier always-opus rule. (Context: an app-side safety layer can re-route the session model invisibly on flagged content; that's outside my control and separate from this setting.)

**How to apply:**
- No `model:` on Agent calls, in skill instructions, or in local agent frontmatter. (The local review-* agents and full-review command had `model: opus` pins removed 2026-06-11.)
- Set a specific model ONLY when the user explicitly asks for one this session.
- Sweep check when touching agent/skill files: `grep -rn "model.*opus\|model.*sonnet\|model.*haiku" .claude/`.

Related: [[feedback_truth_over_optimism]].
