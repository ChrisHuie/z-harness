---
name: feedback-verify-provenance-before-preexisting-claim
description: "Before telling a reviewer a flagged pattern is 'pre-existing' (not introduced by this PR), verify to the hilt — a stable COUNT is not sufficient (the set can churn: remove N, add N). Required: pickaxe `git log -G` over the PR's own commit range (empty = untouched) + byte-identical site-set diff (base vs head) + `git blame`/`log -S` to the introducing commit. 'Pre-existing' ≠ 'harmless'."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 8377e960-8e7a-4aba-8c4d-4aedb89a6629
---

Claiming "pre-existing, not our regression" to a careful reviewer is a fresh
credibility burn if it's wrong. Verify provenance before saying it.

**A stable count is necessary but NOT sufficient** — the same count can hide
churn (the PR removed N old sites and added N new ones). Prove the SET is
unchanged and that no PR commit touched any instance:

1. `git log -G'<pattern>' BASE..HEAD -- <paths>` over the PR's OWN commits —
   empty means no commit added / removed / MODIFIED a matching line.
2. Byte-identical site-set diff: grep the matched statements at BASE vs HEAD,
   strip line numbers, sort, diff — identical = nothing added / moved / changed.
3. `git blame` / `git log -S` the specific lines to the introducing commit;
   confirm it predates the PR's branch point (`git merge-base PRE origin/main`).

**"Pre-existing" ≠ "harmless."** Verify only the provenance you checked; the
reviewer's architectural concern may still be valid. Frame the response as a
SCOPE decision (fold in vs follow-up), not a dispute of the finding.

Pair with [[feedback_verify_before_asserting]] and [[pr_review_audit_workflow]].
