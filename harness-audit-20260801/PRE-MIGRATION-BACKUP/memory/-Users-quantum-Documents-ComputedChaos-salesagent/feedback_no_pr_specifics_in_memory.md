---
name: feedback-no-pr-specifics-in-memory
description: "PR-specific audits, file lists, status snapshots belong in PR comments — never in memory. Memory is for cross-session patterns"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: acdcab63-786c-4cc7-9c58-54f2c30d2c24
---

Per-PR content does NOT go in memory. PR audit findings, status snapshots, file lists, rebase plans, "definition of ready" checklists for a specific PR — all of these belong in PR comments (or chat output the user pastes into a PR), never in `memory/`.

**Why:** The user pushed back: "lets go pr comment body. No reason to add specifics about a pr to memory. That is dumb and not scalable." A PR snapshot:

- Goes stale within hours — new commits invalidate file lists, line numbers, head SHAs, CI state
- Doesn't generalize across conversations — next session may be on a totally different PR
- Pollutes the memory index — every closed PR leaves a dead pointer
- Has a better home — GitHub PR comments are visible to reviewers, persistent, scoped to the PR, naturally surface with `gh pr view`

**How to apply:**

When persisting PR audit findings:
- Output a PR comment body in chat — user pastes into the PR via `gh pr comment <num> --body-file -` or the GitHub UI
- Include the head SHA being audited so reviewers can tell when it's stale
- For ongoing tracking across multiple audits, edit a single PR comment in place, don't add new ones each cycle
- Cross-link related memories with `[[memory-name]]` from the comment body if useful for the reviewer

When something IS worth a memory:
- The *pattern* extracted from the PR (e.g. "boundary ValueErrors should be typed AdCPError") — generalizable
- The *workflow* used to find it (e.g. "always grep all assertion forms before pushing") — reusable
- *Project state* that spans PRs (e.g. "Flask→FastAPI migration phase 2 in flight") — durable

When something is NOT worth a memory:
- "PR #1307 has 46 unique files in these directories" — snapshot, decays
- "A reviewer's 5 asks on PR #1274" — PR-specific
- "Rebase plan when #1306 lands" — temporal, single-use

The rule is: memory's purpose is to make the *next* session smarter at the *general* task, not to substitute for the issue tracker. See [[feedback_planning_doc_location]] and [[feedback_github_issue_drafting]] for related principles.
