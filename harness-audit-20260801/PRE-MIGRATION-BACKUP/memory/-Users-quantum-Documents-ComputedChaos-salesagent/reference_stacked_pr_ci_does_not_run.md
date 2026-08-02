---
name: reference_stacked_pr_ci_does_not_run
description: "CI + CodeQL filter to branches:[main]/[main,develop] — stacked PRs targeting a feature branch never get heavy CI; local Docker suite is the gate"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 77235ac6-73c5-488a-99a2-0abb0f51ef4a
---

The heavy workflows are **base-branch filtered**: `.github/workflows/ci.yml` triggers on `pull_request: branches: [main, develop]`; `codeql.yml` on `pull_request: branches: [main]`. So a **stacked PR** whose base is another feature branch (e.g. #1274 `feature/buying-mode-refine-wireup` → base `feature/property-list-targeting`, not main) gets **NONE of the heavy CI** — no Unit/Integration/E2E/Admin/BDD job and **no CodeQL re-scan**. Only the **unfiltered** workflows run on any PR: `Security` (pip-audit/uv-secure/zizmor), `IPR Agreement`, `PR Title Check`, `pinact`, `actionlint`, `action-semantic-pull-request`.

Consequences:
- **The local full Docker suite (`./run_all_tests.sh ci`) is the ONLY test gate for a stacked PR** — don't wait for CI to validate it; it won't run until the PR re-targets main (after its parent merges). Diagnose via `gh run list --branch <head>` (CI/CodeQL absent for the head sha) and `gh pr view N --json baseRefName`.
- **CodeQL alerts on a stacked PR are frozen** at the last main-targeting scan — a fix you push (e.g. a `loggable()` sanitizer) won't clear them until re-targeting main re-scans. They're advisory in the ramp config (`.github/codeql/codeql-config.yml`); don't block on them, note they'll re-scan later.
- `gh pr checks` showing only ~8 lint/security checks (not Unit/Integration/CodeQL) on a non-main-targeting PR is EXPECTED, not a misconfiguration. `mergeStateStatus=CLEAN` is achievable because the feature-branch base has no required-check/required-review protection (main does).

Note the `Security`/`pip-audit` job DOES run on stacked PRs (unfiltered) and enforces `scripts/security-ignored-vulns.sh`; a stacked PR whose base is behind main on a security dep-bump (transitive, e.g. pydantic-settings/zeep) fails it until the dep is bumped to match main or the base merges current main. See [[gh_actions_dirty_merge_skips_pull_request_workflows]] (a DIRTY PR ALSO skips pull_request workflows — a separate skip mechanism) and [[feedback_run_full_suite_before_every_push]].
