---
name: reference_release_please_pr_ci_mechanics
description: "release-please PRs are GITHUB_TOKEN-authored → ci.yml lands action_required; close/reopen (as human) to run required checks; workflow_dispatch checks don't satisfy the PR gate"
metadata: 
  node_type: memory
  type: reference
  originSessionId: e1914c0a-262b-4409-93ae-320e72503d6a
---

On prebid/salesagent, merging the release-please PR (`chore(main): release X`) is the whole release trigger, but getting it mergeable has non-obvious CI mechanics:

- The release PR is authored by `github-actions[bot]` via `GITHUB_TOKEN`. Its `ci.yml` `pull_request` run lands in **conclusion=`action_required`** (pending approval), so the required **Unit Tests** / **E2E Tests** contexts never report → PR stays `mergeStateStatus: BLOCKED`. Only the CodeQL checks (default-setup) run.
- The `POST /actions/runs/{id}/approve` API returns **"not waiting for approval"** here — that endpoint is fork-PR-only, so it does NOT clear this gate.
- **Fix: close + reopen the PR as a human.** The `reopened` `pull_request` event runs `ci.yml` under your actor (not the bot) → not `action_required` → required checks run and report. (A human-authored commit pushed to the release branch also works, but release-please may force-push over it.)
- A separate **`workflow_dispatch`** run of `ci.yml` does **NOT** attach its checks to the PR's required contexts — they stay on that run; the PR still shows the old/cancelled checks. Only `pull_request`-triggered runs satisfy the PR gate. To re-trigger PR CI, push a commit (or close/reopen), never `workflow_dispatch`.
- Main ruleset: 1 approving review + Unit/E2E required; `current_user_can_bypass: never` (even admins can't bypass). The release PR is bot-authored, so you CAN approve it yourself (you're not the author). A normal human-authored feature PR runs CI normally (no `action_required`).
- A superseded/cancelled check on the same head SHA lingers in `statusCheckRollup` alongside the new one; GitHub evaluates the **latest** check per context, so a fresh SUCCESS supersedes an older CANCELLED. `mergeable` may sit at `UNKNOWN` for a while after approval while GitHub recomputes.

Pairs with [[reference_release_jobs_invisible_to_pr_ci]]: the publish jobs (`build-and-push`, `sign-and-attest`) are gated on `release_created`, so they never run in PR CI and the tag/GitHub Release are cut BEFORE the Docker publish — pre-validate the image (Trivy gate especially) before merging the release PR, or you get a half-release.
