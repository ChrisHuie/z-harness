---
name: Push policy — user controls all pushes
description: Never push (regular OR force) without explicit per-action authorization; user controls all pushes to origin
type: feedback
originSessionId: 73222b09-169f-4917-8149-a9e1e0f97d47
---

<!-- audit-2026-08-01 -->
> **SUPERSEDED as of 2026-08-01.** Duplicates `/Users/quantum/.claude/projects/-Users-quantum-Documents-ComputedChaos-salesagent/memory/feedback_user_owns_git_push.md`, which is kept as the canonical version. Kept for history.
> Rationale: HIGH-trust salesagent twin states the same rule with a better-evidenced exception (explicit delegation -> confirm-once-then-execute) that this absolutist version lacks. Already in ~/.claude/CLAUDE.md.

Never push to origin without explicit per-action authorization, even when the broader workflow implies it. The user runs all `git push` commands themselves — including regular pushes after my commits, and force-pushes after rebases.

**Why:** During Wave 5 of PR #1, I attempted `git push --force-with-lease origin feat/read-skills` after a clean rebase. The user had said "lets proceed to wave 5 please" and I had outlined that Wave 5 included force-push, but they rejected the tool call. Their pattern across all 4 prior waves was: I commit, they push (regular `git push`). Force-push was no exception.

**How to apply:**
- Make the commits, run `git status` / `git log` to show state, and stop.
- Tell the user the suggested push command (e.g., `git push --force-with-lease origin <branch>` for rebased branches; `git push` for regular).
- Wait for the user to confirm "pushed" before continuing.
- Apply this even when an earlier message implied push authorization for the broader phase. Each push is its own action and needs its own confirmation.
- If the user explicitly says "push it" or "go ahead and push" for a specific operation, that's authorization for THAT push only.
