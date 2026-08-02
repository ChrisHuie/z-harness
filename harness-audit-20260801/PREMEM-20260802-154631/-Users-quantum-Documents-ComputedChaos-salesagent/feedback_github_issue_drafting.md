---
name: feedback-github-issue-drafting
description: "\"Create an issue\" = output the body in chat for the user to paste — never gh issue create, never a notes file. Body scopes the GAP and contract, not the solution; ~one GitHub page."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: eea6a61f-fb14-405a-8a08-b5c73900ce1c
---

(Merges feedback_no_notes_for_github_issues + feedback_issue_body_scope, 2026-06-11.)

**Delivery:** "create an issue" / "I want to create a thorough issue" means produce the issue body inline in chat so the user can paste it into GitHub themselves. Do NOT run `gh issue create` (the user files from their own account — same shape as [[feedback_user_owns_git_push]]; all GitHub-mutating commands are user-owned by default). Do NOT stash the draft in `.claude/notes/` ("Dumb to add notes for every issue we fix to a random claude folder!"). Long bodies are fine in chat — keep them scannable with headers, in a fenced block per [[feedback_no_blockquote_for_pasteable_text]].

**Scope:** issues are scoping artifacts, not design RFCs — they answer what is missing, what the spec/contract requires, and what "done" looks like. User reaction to a prescriptive 700-liner: "It's too long for github... you just went and decided your own plan proposal? How do we know that is a good one?" Issues anchor the contract; PRs argue the design.

Include:
- Title + 2–3 sentence summary; impact bullets (what's blocked, who's affected)
- What the spec/contract requires (compact, linked, key fields/rules)
- Current gap (short, with codebase pointers)
- Implementer-beware notes — non-obvious FACTS (library quirks, spec gotchas), not solutions
- Acceptance criteria as OUTCOMES, not steps
- Open design questions; out-of-scope/dependencies; terse reference permalinks

Exclude: pseudocode/signatures for the proposed implementation; design alternatives with pros/cons; step-by-step or file-by-file plans; exhaustive test-function inventories; the verification dump itself (verification informs the issue, it doesn't fill it).

Length signal: ~one GitHub page (150–250 lines); 700 is too long.
