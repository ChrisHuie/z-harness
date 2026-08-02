---
name: feedback-principled-scope-expansion
description: "When deciding whether scope expansion in a PR is OK, the test is not 'is this in the PR title?' but 'does the expansion let the PR land at a consistently better state with the principal intact?' Plumbing fixes that complete the principal are OK; unrelated drive-by refactors are not."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: acdcab63-786c-4cc7-9c58-54f2c30d2c24
---

When asked to expand PR scope, the right test is **not** "is this strictly in the PR title?" — it's **two questions in sequence**:

1. **Does the expansion let the PR land at a more consistent/correct end state?**
2. **Does the PR's principal (its core purpose) remain intact?**

If both are yes → expansion is principled and OK.
If either is no → don't expand; defer or split.

**Examples of OK expansion (do the work, don't defer):**

- PR principal = wire-level error-emission tests. Two A2A skills aren't reachable via real wire because the dispatcher's skill_handlers map doesn't route them (2-line gap). Adding those 2 entries IS the principal — without it, the tests can't actually exercise the wire and fall back to handler-layer asserts. Expansion is the completion of the principal, not a divergence from it.
- PR principal = correct stale spec citations. Touching a file triggers a ruff full-file scan that surfaces 3 pre-existing UP042 violations. Fixing UP042 (StrEnum swap) is required to make the principal's commits land at all. Without the fix, the commit is blocked, the principal can't ship. Expansion is unblocking, not drifting.

**Examples of NOT OK expansion (defer or split):**

- "While I'm in here, let me refactor unrelated helper X" — doesn't complete the principal, opens new review surface, ages the PR.
- "Let me add a new feature flag that's been on my list" — different category of work, no causal link to the principal.
- Bulk linter rewrites (`ruff --unsafe-fixes`, mass black reformat) during any focused PR — see [[feedback_no_unsafe_autofix]].
- Adding planned-for-later refactors because "now's a good time" — they belong in their own PR.

**The contract intact / completed distinction:**

- "Principal stays intact" means a reviewer reading the PR title + description can still recognize what they're reviewing. The expansion is plumbing that makes the principal work, not a different goal.
- If the expansion forces you to change the PR title, you're drifting, not expanding.

**Watch your own bias:** the strongest temptation for unprincipled scope expansion is when the unrelated cleanup is obviously small. Small ≠ in-scope. Apply the two-question test, not the size test.
