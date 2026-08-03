---
name: feedback_reverify_pr_head_before_and_after_fanout
description: Re-check the live PR head right before AND after fanning out reviewers; an active PR moves mid-review
metadata: 
  node_type: memory
  type: feedback
  originSessionId: aae21ff1-43ff-448b-a554-ea0658231c89
---

When reviewing an ACTIVE PR (recent `createdAt`/`updatedAt`, author or co-authoring agent still pushing), the head SHA can move while your review runs. In the PR #1543 review, I fetched `pull/1543/head` at session start (got commit `7ccc2efc7`), briefed all 5 harness specialists to review that SHA, and the author pushed commit 2 (`387eb516a`, "address review") ~40 min later — DURING the fan-out. All 5 reviewers reviewed the stale first commit; only the spec-conformance agent caught it (via `gh api repos/O/R/commits/<sha>` + `gh pr view --json headRefOid`). Commit 2 had already fixed several findings (obligation-doc contradiction, BDD subset→exact-set, duplicated literal, list→tuple).

**Why:** a fan-out of N expensive agents against a stale SHA wastes the run and produces findings the author already addressed — you look like you didn't read their latest push.

**How to apply:**
- Before launch: `gh pr view N --json headRefOid,updatedAt,commits` and fetch THAT sha; pin every subagent brief to it.
- After all agents return, re-run `gh pr view N --json headRefOid` and diff head-then vs head-now (`git diff <reviewed> <current>`) BEFORE consolidating. Re-base every finding onto the current head; tag each as still-present / fixed-in-later-commit (verify the "fixed" ones yourself — don't trust the diff summary alone).
- Tell subagents in their brief to assert the head SHA themselves and abort/flag if it moved.
Links: [[feedback_verify_branch_currency_before_rebuild]], [[feedback_verify_branch_runs_assert_head]], [[feedback_detecting_subagent_overconfidence]]
