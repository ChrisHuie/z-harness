---
name: feedback_issue_vs_pr_number
description: "GitHub issue numbers and PR numbers share one per-repo counter, so a PR opened after an issue gets a different, later number — they never match. Verify the real PR number; never reuse the issue number as the PR/branch label. Applies to every repo."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: e3ad56ad-91fe-4dc9-9436-178e2601ff58
---

GitHub issues and pull requests draw from ONE shared per-repo numbering sequence, so a PR opened after you file an issue always gets a different (later) number. The two are never interchangeable.

**Why:** Conflating them puts wrong identifiers in conversation, commit/PR bodies, and status reports — the user has to stop and correct it, and a wrong number misleads anyone reading later. (Filed issue #1394 on salesagent, named the worktree `salesagent-1394`, then repeatedly called the admin-fix PR "#1394" when it was actually PR #1395.)

**How to apply:** Treat issue# and PR# as separate identifiers from the start. After a PR exists, confirm its number with `gh pr list --head <branch> --json number,url` (or `gh pr view <branch>`) before referring to it. In a PR body, `Closes #<n>` points at the ISSUE; the PR carries its own number. Never infer the PR number from the issue, and don't let a worktree/branch named after the issue lull you into reusing that number for the PR. A specific, recurring case of [[feedback_verify_before_asserting]].
