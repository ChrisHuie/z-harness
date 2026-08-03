---
name: pr-review-audit-workflow
description: "Required steps before claiming any PR review feedback is \"addressed\" — three endpoints, item-level checklist, diff-based verification"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: acdcab63-786c-4cc7-9c58-54f2c30d2c24
---

When auditing PR review feedback for a "have we addressed everything?" claim,
the verification MUST follow this checklist. Shortcutting it produces missed
items.

**Why:** PR #1276 missed 8 R1 inline comments + 7 hand-rolled identity sites
across multiple verification rounds because the audit was incomplete. GitHub
stores PR feedback in THREE separate API endpoints:

- `gh api repos/.../pulls/N/reviews` → review BODIES (the narrative summary)
- `gh api repos/.../pulls/N/comments` → INLINE comments on specific file:line
- `gh api repos/.../issues/N/comments` → general PR conversation

Querying only one misses critical feedback. GraphQL `reviewThreads` also
shows thread resolution state (`isResolved`, `isOutdated`).

**How to apply:**

1. **Pull all three endpoints upfront** (not after, not "if needed"):

   ```bash
   gh api repos/OWNER/REPO/pulls/N/reviews
   gh api repos/OWNER/REPO/pulls/N/comments
   gh api repos/OWNER/REPO/issues/N/comments
   gh api graphql -f query='{ repository(owner:"OWNER", name:"REPO"){
       pullRequest(number:N){ reviewThreads(first:50){
         nodes{ isResolved isOutdated path comments(first:10){
           nodes{ author{login} body createdAt }}}}}}}'
   ```

2. **Build a flat item-level checklist** with file:line + verification command
   per item. "Review 3 has 7 items" is not a checklist; `[ ] R3.1 at
   path.py:42 verified via 'git show <sha>:path.py | grep ...'` is.

3. **Treat composite comments as multiple items.** A comment saying "fix X.
   Same for Y" is TWO items. Each gets its own checkbox.

4. **Verify each item with a code diff**, not commit messages.
   `git show <review-commit>:path` shows the original;
   `git diff <sha>..HEAD path` shows what changed. The diff is the proof —
   commit messages describe intent, not completeness.

5. **Only after every item has a green check** draft the user-facing PR
   comment. Comment structure should mirror the checklist (sections per
   review, items per feedback).

6. **If asked "did we address X?"** — never shortcut by recalling. Re-query
   the endpoints and verify the diff. Codebase is truth.

7. **Check thread state.** An ACTIVE thread (not RESOLVED, not OUTDATED) on
   GraphQL means the underlying code still matches the comment's context —
   even if we technically fixed the issue, GitHub didn't auto-resolve. When
   posting the consolidated comment, reply to each ACTIVE thread directly so
   the reviewer sees it explicitly addressed.

Pair with [[feedback-pattern-extraction]] — auditing the cited site is step
1; auditing the codebase for the same PATTERN at other sites is step 2.
