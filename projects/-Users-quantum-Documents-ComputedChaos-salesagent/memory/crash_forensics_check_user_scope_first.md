---
name: crash-forensics-check-user-scope-first
description: "After a crash/power-cut, verify survival in the USER'S stated scope (CWD project sessions) first; meta.json-without-jsonl = lost agent transcripts; never declare \"everything survived\" from the biggest artifact found."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 3dbd56d7-dad5-4261-8c87-dd40fa02c90a
---

2026-06-10 power cut killed two sessions. I found the largest surviving transcript (7.6MB, #1312 planning) and declared "everything survived — you lost nothing durable." The user's actual question was about 3 review passes on #1399 run in the CWD worktree — that session's transcripts were destroyed (132-byte stub, agent meta.json files only). I then spent 4 turns steering them to #1312 and "correcting" them while they repeatedly said "1399". User: "you BS-ed me... wasted my time arguing and telling me I was wrong."

**Why:** anchored on the biggest/most-recent artifact + happy-path optimism ([[feedback-truth-over-optimism]]); never enumerated the CWD project dir's sessions before answering ([[feedback-verify-before-asserting]]).

**How to apply:**
1. "Anything saved?" after a crash → FIRST enumerate `~/.claude/projects/<CWD-project>/` sessions (users ask from the directory they care about), then widen outward.
2. Crash signature: subagent `*.meta.json` present but `agent-*.jsonl` absent + parent transcript ~100 bytes = transcripts lost (meta flushed at spawn; transcript writes buffered). `~/.claude/history.jsonl` prompts from the same window are lost too.
3. Loss checklist before any verdict: git (log/reflog/stash/status across ALL worktrees), `.claude/notes/`, `test-results/`, `~/.claude/tasks/<session>/`, `tmutil listlocalsnapshots /`, iTerm2 SavedState/AutoLog. APFS journals metadata only — file content is unrecoverable.
4. The user's repeated correction outranks my artifact pattern-match. Two corrections on the same point = stop, re-verify their claim from scratch.
5. Read-only review passes leave no repo artifacts — if tree is clean and HEAD unmoved, the findings lived only in transcripts. Recovery = re-run (input state is reproducible); offer that, with findings written to a local file incrementally so the next cut can't eat them.

Power cuts recur for this user — see [[docker-desktop-stale-singleton-after-crash]].
