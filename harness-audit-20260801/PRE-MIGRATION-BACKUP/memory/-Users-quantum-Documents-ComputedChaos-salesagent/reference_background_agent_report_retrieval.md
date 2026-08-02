---
name: reference_background_agent_report_retrieval
description: "Background Agent-tool subagents may idle without pushing their final report to main; retrieve via SendMessage, never Read the .output symlink"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 72b5eab3-5772-4ea8-ac45-69eac1644028
---

A subagent spawned via the Agent tool with `run_in_background: true` may, on finishing, emit `idle_notification` (idleReason "available") pings to main **instead of** delivering its final report — its findings do NOT auto-arrive as a message.

**How to get the report:** `SendMessage` the agent a bounded ask ("reply to main in ONE short message, <250 words, no transcript: 1) blockers? 2) anything beyond <list>? 3) confirm clean state"). It replies with an `<agent-message>` you can act on.

**Never** `TaskOutput`/`Read` the agent's `.output` file for a local_agent — it symlinks the full JSONL transcript and overflows context. `TaskOutput` by the display name also fails ("No task found").

**Prevention:** when spawning a background agent for a report, instruct it explicitly to `SendMessage` its final structured report to `main` on completion, so you don't have to pull it. Still verify its claims yourself per [[feedback_detecting_subagent_overconfidence]] — re-run any command it cites that you didn't personally run (in a separate worktree to avoid colliding with the agent's checkout). Model inheritance + Step-0 reads still apply ([[feedback_subagent_model_inherit]], [[feedback_subagents_need_explicit_read]]).
