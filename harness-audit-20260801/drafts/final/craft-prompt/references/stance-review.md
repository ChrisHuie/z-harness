verified: 2026-07-14 · sources: modes-and-composition §2/§5/§6/§7/§9 (stance table, routing, enforcement, handoffs), concepts M3/M7 (C6)
conformance: craft-prompt eval 015

# Stance: review

**Job:** judge a diff/PR and report findings — change nothing. Initiative I0 (report-only).

## Envelope
- **Tool posture:** read-only (read/grep the diff and its context). No edits.
- **Context gathering:** exhaustive *within scope* — the diff/PR is the boundary; read all of it, don't wander the whole repo.
- **Policy blocks:** self-reflection (adversarial self-verify). The review phase is bounded by its read-only envelope, so render neither action-default side and no persistence block. Side B's conditional edit grant conflicts with that envelope; an offer to fix is a handoff outside the current review phase.
- **Verification:** adversarial self-verify each finding; hit a precision target — no finding spam. A false finding costs more than a missed nit.

## Output / handoff
Severity-ranked findings (critical / warning / suggestion), each with **why + a concrete fix**. Consumes: the diff (+ project conventions to cut false positives). Followed by **fix** (implement stance re-entered, consuming the findings) or **commit**.

## Routing — entering / leaving
- **Enter when:** user asks to review/judge existing work without requesting changes. When torn between review and implement, review first.
- **Leave when:** "review and fix the criticals" → run the findings phase in review, then transition to implement with findings as input; the fix was already requested, so do not re-offer it. When no fix was requested, end by offering the transition ("want me to fix the criticals?").
- **Continuous re-routing:** a mid-session redirect re-routes immediately; acknowledge the switch. Explicit invocation is the top signal (M7); harness-enforced mode supersedes it (M3).

## Enforcement (read-only)
- **Claude Code:** permission rules + PreToolUse hook deny writes (the enforcement); frontmatter `allowed-tools: Read, Grep, Glob` is advisory permission-smoothing only, not a restriction (verified 2026-07-14, claude-code#37683).
- **Codex:** `sandbox_mode: read-only` + approval policy.
- **Fallback (any harness):** prose hard-block in the `STRICTLY FORBIDDEN` register (caps justified — mode gate). No write tools ever appear in a review skill's `allowed-tools` (stance-consistency lint).

A harness adapter must pair the prose contract with read-only enforcement configuration when the harness supports it. Both are compiler outputs; enforcement configuration is deployment metadata, not review-task output.
