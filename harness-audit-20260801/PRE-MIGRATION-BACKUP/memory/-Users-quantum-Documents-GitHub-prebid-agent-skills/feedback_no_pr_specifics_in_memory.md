---
name: feedback-no-pr-specifics-in-memory
description: "PR-specific audits, file lists, line numbers, status snapshots belong in PR comments / chat — NOT in memory. Memory is for cross-session patterns and durable project state only."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: aa049dfd-aa09-4a10-a1e2-61f821d8e096
---

<!-- audit-2026-08-01 -->
> **SUPERSEDED as of 2026-08-01.** Duplicates `/Users/quantum/.claude/projects/-Users-quantum-Documents-ComputedChaos-salesagent/memory/feedback_no_pr_specifics_in_memory.md`, which is kept as the canonical version. Kept for history.
> Rationale: Identically-named HIGH-trust twin in salesagent; this copy self-declares as a port. Keep the salesagent original.


Per-PR content does NOT go in memory. PR audit findings, status snapshots ("A1 done, A2 done…"), file lists, fixture names, line numbers, head SHAs, rebase plans, per-PR "definition of ready" checklists — all belong in PR comments (or chat output the user pastes into a PR), never in `memory/`.

**Why:** The user: "No reason to add specifics about a pr to memory. That is dumb and not scalable." A PR snapshot goes stale within hours (new commits invalidate file lists / line numbers / SHAs / CI state), doesn't generalize to the next conversation, and pollutes the memory index with dead pointers. GitHub PR comments are the better home — persistent, scoped, visible to reviewers, surface with `gh pr view`. (General working-style preference; was siloed in the salesagent project — ported.)

**What IS worth a memory:** the generalizable *pattern* extracted from the PR, the reusable *workflow* used to find it, and durable *project state* that spans PRs/sessions (e.g. "Workstream B [harden skills] pending"). NOT the per-PR snapshot.

**How to apply:** When persisting PR audit/status, output a PR-comment body in chat (in a fenced code block per [[feedback-no-blockquote-for-pasteable-text]]) for the user to paste; include the head SHA so staleness is visible. Keep memory to the lesson + durable state. Related: [[feedback-no-notes-for-github-issues]], [[feedback-no-planning-artifact-for-small-tasks]].
