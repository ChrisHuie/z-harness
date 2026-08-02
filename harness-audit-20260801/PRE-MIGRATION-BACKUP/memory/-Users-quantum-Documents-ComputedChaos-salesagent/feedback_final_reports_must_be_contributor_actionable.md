---
name: final-reports-must-be-contributor-actionable
description: "A \"final report\" on a PR review = contributor-actionable document (per-item location/problem/why/exact tested diff/verify), not an audit-status summary; never reference local paths like /tmp patches as the deliverable."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: a5b1ae6c-5f3d-49b7-8cab-32d1cb82954a
---

After multi-pass PR review work, when the user asks for a "final report," the deliverable is a **self-contained review document the contributor can act on**, not a verification-status summary for the maintainer.

**Why:** On PR #1372 I produced a status table + "fixes are in /tmp/pr1372-improvements.patch" — useless to the contributor (local path, one-line item summaries). User: "not much to help a contributor fix anything?? WTF."

**How to apply:**
- Per item: exact file:line → what's wrong → why it matters (concrete, measured) → the literal tested diff → verification notes.
- Self-contained: no `/tmp` paths, no references to "my earlier pass"; evidence stated impersonally.
- GitHub-paste-safe: wrap diffs that contain triple-backtick lines in four-backtick fences.
- Audit-trail/raw-state details go in a short maintainer addendum AFTER the document, not in its body.
- Distinct from [[feedback_github_issue_drafting]]: GitHub ISSUE bodies describe gap/contract only (no solutions); PR review fix reports carry full solutions — opposite polarity, different artifact.
