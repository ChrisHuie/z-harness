---
name: rereview-diff-against-current-main-not-mergebase
description: "Re-reviewing a stale-based PR: the three-dot (merge-base) diff hides commits whose content already landed on main via sibling PRs; diff two-dot vs CURRENT main + blame to catch redundant/duplicate commits and rebase-needs"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: bd556aef-fe28-4425-a1d1-8b080eae4100
  modified: 2026-07-21T10:38:34.163Z
---

When re-reviewing a PR that is **behind main**, the standard review diff `git diff origin/main...HEAD` (three-dot = merge-base→head) shows every PR commit as a legitimate addition — even commits whose identical content has ALREADY merged to main via a sibling PR while this one sat open. The specialist reviewers all diff three-dot, so they validate such a commit's code on its own merits and never flag that it is redundant with current main.

**Why it matters:** on a re-review, a stale-based PR can carry commits that are pure no-ops against current main (already-upstream), or that duplicate an in-flight sibling PR. Merging as-is muddies history (a `fix(deps)`/`fix(ci)` commit attributes to this PR a fix main already has) and skips a needed rebase. This is the highest-value class of finding the fan-out misses because it is invisible in the three-dot diff.

**How to apply (main-session, before/alongside the fan-out):**
- `git merge-base origin/main HEAD` then compare: three-dot (what the PR *thinks* it adds) vs two-dot `git diff origin/main HEAD` (what actually differs from CURRENT main). Files/hunks present in three-dot but ABSENT from two-dot are already on main.
- For any dep/CI/config hunk: `git show origin/main:<file>` + `git blame origin/main -L n,n -- <file>` + `git log origin/main -S '<string>' -- <file>` to prove which sibling PR landed it. A byte-identical file (absent from the two-dot stat) = already upstream.
- Check `gh pr list --state open` for an in-flight sibling doing the same work (the author may even name it in the PR body).
- Recommend **rebase onto current main** — it drops already-upstream commits and re-runs CI against today's main (which may have moved: SDK bumps, new tests). Verified live on a #1665 re-review: mcp CVE bump + pinact `-no-api` were both already on main (sibling PRs), the free-disk step duplicated an in-flight PR, and a real BLOCKER (a stale hardcoded transport set the PR *activated*) was only catchable by running the tool against real data, not by reading the three-dot diff. [[feedback_verify_provenance_before_preexisting_claim]] [[feedback_merge_creates_duplication_sweep_ssot]] [[feedback_diff_scope_hides_duplicate_twin]] [[feedback_empirical_over_static_guard_assessment]]
