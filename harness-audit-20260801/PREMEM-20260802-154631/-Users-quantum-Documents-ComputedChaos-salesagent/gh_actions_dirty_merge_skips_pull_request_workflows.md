---
name: gh-actions-dirty-merge-skips-pull-request-workflows
description: "When a PR has mergeable_state=dirty (merge conflict), GitHub Actions skips pull_request workflows. Only pull_request_target workflows run. Diagnosis path for \"tests aren't running\"."
metadata: 
  node_type: memory
  type: reference
  originSessionId: acdcab63-786c-4cc7-9c58-54f2c30d2c24
---

When CI appears to not run on a PR after a push:

**Symptom:** Lightweight workflows (PR Title Check, IPR Agreement) run but Test Suite, Security, CodeQL don't.

**Diagnosis:**
```bash
gh pr view <N> --json mergeable,mergeStateStatus -q '"mergeable=\(.mergeable) state=\(.mergeStateStatus)"'
```

If output is `mergeable=false state=dirty` (or `mergeable=CONFLICTING state=DIRTY`), GitHub Actions cannot generate the synthetic merge commit (`refs/pull/<N>/merge`) that `pull_request` events check out. So those workflows are silently skipped.

**Why only PR Title Check / IPR Agreement still run:** They use `pull_request_target` event, which checks out the source branch directly without needing a merge commit. This means `mergeStateStatus: dirty` doesn't block them.

**Fix:** Merge or rebase main into the PR branch to clear the conflict. Once `mergeable=MERGEABLE`, the next push (or a `synchronize` event) triggers full CI.

**Post-push assertion (MANDATORY, learned 2026-07-07 on #1389):** after every push to a PR branch, before claiming "CI is running", assert BOTH:
```bash
gh pr view <N> --json mergeable,mergeStateStatus -q '"\(.mergeable) \(.mergeStateStatus)"'   # not CONFLICTING/DIRTY
gh run list --commit <pushed-sha> --json workflowName,status                                  # runs EXIST for the SHA
```
An empty run list for the pushed SHA IS this failure mode — checks pages show the stale previous run, which reads as "frozen tests".

**How a branch BECOMES dirty non-obviously:** cherry-picking one of main's commits onto the branch. Main keeps evolving the same files after that commit, so the duplicated-but-diverged content conflicts when GitHub builds the merge ref — even though the cherry-pick itself applied cleanly. On #1389, cherry-picking main's ruff-py312 bump (#1519) turned a MERGEABLE PR CONFLICTING because #1541 had since touched the same helpers on main. When the branch needs something from main, MERGE main (the full state), don't cherry-pick a slice of it.

**Watch out for:**

1. **Pre-commit black/ruff oscillation on merge commits** ([[feedback_black_ruff_format_disagreement]]) — may require `--no-verify` with explicit user authorization
2. **`.ast-grep/rules/` missing** — the project's ast-grep pre-commit hook errors if `.ast-grep/rules/` doesn't exist; needs a placeholder file + `sgconfig.yml` at repo root. PR #1306 added these files; copy from there if missing
3. **`.gitleaks.toml` for test-only secrets** — `.claude/skills/.agent-db.env` contains test-only ENCRYPTION_KEY; needs allowlist entry. PR #1306 added the `.gitleaks.toml`
4. **`git reset HEAD --` during conflict resolution can drop tracked files** — verify the merge commit's tree contains everything you intended via `git diff origin/main..HEAD -- '.claude/' '.creative-agent-catalog.json'` etc.

Related: [[feedback_run_full_suite_before_every_push]] — green CI locally doesn't catch this; GitHub-side merge state does.
