---
name: feedback_pr_base_current_main_push_origin
description: "salesagent PRs push to origin (prebid/salesagent) rebased onto CURRENT origin/main; fetch+rebase before opening, don't trust the stale local origin/main ref"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: adb9943e-db7b-4882-b8ec-ea860a6c56c6
---

In salesagent, open PRs against `origin` = github.com/prebid/salesagent, NOT the fork remotes that also exist locally (`github-desktop-affinity-com` → affinity-com/salesagent, `konstantine-1335` → KonstantinMirin/prebid-salesagent). The user works off main directly and has push access to origin. Base every PR on the **current** main: `git fetch origin` and rebase before opening, because the local `origin/main` ref is routinely stale (main advances between sessions — observed 2026-07-06: local origin/main was one commit behind).

**Why:** the user explicitly requires the PR "based off current version of main." When asked which of the 3 remotes to push to, the answer was "we are working off main" → push origin, rebase onto latest main. Asking cost a round-trip; default to origin + fresh rebase.

**How to apply:** cut branch off `origin/main --no-track` → make changes → before push: `git fetch origin`; if `origin/main` advanced, `git rebase origin/main`; verify `git diff --stat origin/main HEAD` shows only intended files + clean tree → `UV_FROZEN=1 git push -u origin <branch>` (uv-run pre-push hooks re-resolve uv.lock otherwise, per [[uv_frozen_for_commit_drift]]) → `gh pr create --repo prebid/salesagent --base main --head <branch>`. Still confirm once before the push per [[feedback_user_owns_git_push]]. Related: [[feedback_feature_branch_first]], [[feedback_verify_branch_currency_before_rebuild]].
