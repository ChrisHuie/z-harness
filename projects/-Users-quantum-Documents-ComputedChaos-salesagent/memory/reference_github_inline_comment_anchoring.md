---
name: reference-github-inline-comment-anchoring
description: "GitHub only accepts a review inline comment on a line present in the PR's diff hunks (added OR context). Findings anchored elsewhere 422 or land silently misplaced — compute the commentable set from the diff before building the payload."
metadata: 
  node_type: memory
  type: reference
  originSessionId: 3417a11b-189e-4cd7-9455-26497192afe0
  modified: 2026-07-31T04:23:33.694Z
---

The charter mandates posting findings as anchored THREADS rather than one
PR-level comment. The constraint that shapes it: `POST
/repos/{o}/{r}/pulls/{n}/reviews` accepts a `comments[]` entry only when
`line` is a new-file line **present in a diff hunk** — added (`+`) or CONTEXT
(` `) lines both work, removed lines and anything outside the hunks do not.
Files absent from the diff cannot be anchored at all. Real reviews routinely
want to cite lines outside the hunks, so this must be resolved deliberately
rather than discovered via a 422.

**How to apply — build, validate, post, then verify:**

1. Dump the diff and parse the commentable set per file. Walk hunk headers
   `@@ -a,b +c,d @@`, advance the new-file counter on `+` and ` ` lines, do not
   advance on `-`:
   ```python
   m = re.match(r'@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@', ln)   # newno = int(m.group(1))
   ```
2. **If the anchor is outside the set, that is a SCOPE SIGNAL, not a formatting
   problem — do not fall back to "nearest commentable line."** An anchor GitHub
   refuses usually means the finding is about code the PR did not change, and a
   diff comment asking an author to edit untouched code is scope creep. Triage in
   this order:
   - Is the **fix target** a line the PR added? If not, the finding belongs in the
     review BODY under "pre-existing, named but not folded in" — never as a thread.
   - If the fix target IS a PR-added line and only the anchor is off (an
     off-by-one onto a closing `"""`, say), anchor on the added line itself.
   - Only if the finding is genuinely about changed behaviour whose statement spans
     a context line may you anchor nearby — and then only within the **same
     statement or the same function**, disclosing the move in the first line.
   The failure this exists for: I relocated five anchors to nearest-commentable
   lines. One landed in a different function from its subject
   (`on_message_send_stream` vs `on_message_send`, 53 lines away), one on an
   unrelated ctor kwarg, and three of the five were about lines byte-identical at
   `origin/main` — so a scope note became a review comment on an outside
   contributor's diff. The referent caught all of it with "why are we making
   comments on code not touched in this pr?", and the repair cost 3 deletions plus
   a public correction. The line-number CONTENT was right in every case; the
   delivery was the defect.
3. Findings whose file is not in the diff at all, plus anything about the PR
   DESCRIPTION, go in the review `body` under an explicit
   "findings with no diff anchor" heading.
4. Assert every anchor against the set BEFORE posting, and assert no duplicate
   `(path, line)` — two comments on one line collapse confusingly.
5. `gh api ... --method POST --input payload.json` with
   `{commit_id, event: "COMMENT", body, comments: [{path, line, side: "RIGHT", body}]}`.
   Pin `commit_id` to the head you reviewed. Use `COMMENT`, not
   `APPROVE`/`REQUEST_CHANGES` — the verdict is the user's.
6. **Verify the comments landed**, because the review can post with the body
   while comments are dropped:
   `gh api "repos/{o}/{r}/pulls/{n}/comments?per_page=100" --jq '[.[] | select(.pull_request_review_id == <id>)] | length'`
   and eyeball the `path:line` list against your intent.

Bodies are markdown and support fenced blocks, so probe output and the exact
proposed edit both belong inside the thread rather than in the summary.

**Pre-post gate — run this instead of trusting the anchor set alone.** For every
intended thread, compute whether its FIX TARGET intersects the PR's added lines
(the `+` set, NOT `+` ∪ context). Any finding with an empty intersection is a
body item, not a thread. Two legitimate exceptions, both worth stating in the
comment so the scoping does not look arbitrary: (a) the fix ADDS new code (a
missing test for the change) rather than editing a line; (b) an untouched line
became stale *because of* a line the PR did change — e.g. a module docstring
saying "scans X and Y" one line above a `SCAN_DIRS` the PR widened.

Related: [[feedback_findings_need_anchors_post_as_threads]] (why threads at all),
[[feedback_user_owns_git_push]] (posting needs explicit go-ahead each time).
