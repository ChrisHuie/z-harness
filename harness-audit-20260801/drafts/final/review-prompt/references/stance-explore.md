verified: 2026-07-14 · sources: modes-and-composition §2/§5/§6/§7 (stance table, routing, enforcement, handoffs), concepts M3/M7 (C6)

# Stance: explore

**Job:** understand a system, answer a question, diagnose — change nothing. Initiative I0 (report-only).

## Envelope
- **Tool posture:** read-only (read/grep/search). No writes, edits, or effectful exec.
- **Context gathering:** broad, just-in-time — cast wide, load on demand; store lightweight identifiers (paths, queries) over pre-loading.
- **Policy blocks:** action-default Side B (`do_not_act_before_instructions`) when the task might still act (latent or escalation-path actions); a pure read/transform task gets neither action-default side. Plus context-gathering (broad variant). Render neither persistence nor `default_to_action` here.
- **Verification:** every claim cites `file:line`. Show evidence, not assertion.

## Output / handoff
Answers and notes grounded in code citations; mutates nothing. Any findings are notes for the next stance, not edits. Feeds **plan** (decide what to do) or a small direct **implement**. Consumes: the user's question or task.

## Routing — entering / leaving
- **Enter when:** user asks a question, describes a problem, or requests analysis *without* requesting changes. The default under ambiguity (conservative-selection: pick the read-only stance when intent is unclear).
- **Leave when:** the user approves an action or requests a change → re-route to plan or implement.
- **Continuous re-routing:** a mid-session correction ("actually, just tell me" / an explicit stance invocation) re-routes immediately — acknowledge the switch, then adopt the new envelope. Explicit invocation is the top routing signal (M7); a harness-enforced mode still supersedes it (M3).
- End by offering the write: "here's the fix I'd make — want me to apply it?"

## Enforcement (read-only)
- **Claude Code:** permission rules + PreToolUse hook deny writes (the enforcement); frontmatter `allowed-tools` is advisory permission-smoothing only, not a restriction (verified 2026-07-14, claude-code#37683).
- **Codex:** `sandbox_mode: read-only` + approval policy.
- **Fallback (any harness):** prose hard-block in the opencode `STRICTLY FORBIDDEN` register (caps justified — it is a mode gate).

Emit both: enforcement config where the harness supports it, prose block as belt-and-suspenders where it does not.
