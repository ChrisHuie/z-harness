---
name: feedback-github-ci-review-blind-spots
description: "Three .github/ CI-review blind spots the src-focused catalog + mechanized ratchets miss on their own: (1) the DRY ratchet doesn't scan .github/ so workflow run:-body copy-paste is invisible; (2) gate/security logic in a run: heredoc is untestable-by-construction (extraction is the prerequisite for coverage, not 'add tests'); (3) a security-workflow change can move WHICH events it runs on and relocate the merge-block to external branch-protection config — diff triggers vs BASE, don't just read the new file."
metadata:
  node_type: memory
  type: feedback
  originSessionId: 0f5ee821-1d49-4243-9edb-0da0a0117e63
  modified: 2026-07-23T21:57:31.505Z
---

When reviewing a `.github/` (CI / workflow) diff, three things the `src`-focused catalog reviewers and the mechanized ratchets do NOT catch on their own:

1. **`.github/` is a DRY blind spot.** The repo dup ratchet (`.pre-commit-hooks/check_code_duplication.py`) scans only `SCOPES=("src","tests","scripts")`. Workflow/composite `run:` heredoc bodies copy-pasted across jobs are invisible to it — most dangerous on a security gate, where two hand-synced verifiers silently diverge. → run the personal detector `.claude/rules/private/detectors/github_workflow_duplication.py .github` (longest identical `run:` block between every pair of jobs/composites; self-tested). Wired into the review-code-patterns agent's DRY cluster.

2. **Gate/security logic in a `run:` heredoc is untestable-by-construction.** A branch-heavy shell/python heredoc that DECIDES an allow/deny (who may bypass a signature check, whether a job fails closed) has no unit any test can target — extraction to a `scripts/ci/*` module is the PREREQUISITE for coverage, so "add tests" is insufficient; flag the heredoc itself. Wired into review-code-patterns + review-security.

3. **Enforcement-model change: does the gate still gate?** For a security/compliance workflow change, diff triggers + gating against BASE (`git show origin/main:.github/workflows/<wf>.yml`), don't just read the new file. A gate can move which events it runs on (per-push `pull_request[_target]` → comment-only `issue_comment`) and relocate the actual merge-block to external branch-protection config not in the repo. Ask: on a FRESH, never-commented unsigned PR, what still blocks merge? Wired into review-security.

**Why:** on a security-gate CI PR, a maintainer round caught a verbatim-duplicated verify body across two jobs (spot 1) and that the branch-heavy verify logic shipped with zero coverage because it lived only as inline YAML — extraction was the prerequisite (spot 2); both were invisible to the mechanized floors and absent from the catalog. Separately, our own security pass caught the enforcement-model change (spot 3) that BOTH human rounds missed. The generalizable class: `.github/` is under-instrumented relative to `src/`, and a CI gate's real teeth are its trigger model + external ruleset, not the code a diff-read sees. Also — the guard for a privileged CI job typically pins SOME fields (checkout `ref`) but not siblings (`repository:` override → fork code with the write token, `persist-credentials`, `set -e`/`continue-on-error` on the verify step): sibling-sweep every pinned field.

**How to apply:** on any `.github/` diff, run `github_workflow_duplication.py`, flag gate-logic heredocs for extraction, sibling-sweep the privileged-job guards, and diff the workflow's triggers/gating vs BASE. The detector + agent edits are the deliverable; this note is the pointer.

Related: [[feedback_guard_matcher_completeness]], [[feedback_semantic_ssot_defect_class]], [[feedback_claimed_invariant_needs_failing_oracle]], [[feedback_escalate_recurring_lessons_to_guards]], [[feedback_personal_harness_gitignored_only]], [[reference_per_diff_review_detectors]].
