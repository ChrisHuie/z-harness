---
name: reference_github_code_quality_no_path_exclusion
description: "GitHub Code Quality bot has NO path-exclusion setting (as of 2026-07, roadmapped later 2026); blocks"
metadata: 
  node_type: memory
  type: reference
  originSessionId: d0eebbf2-8f42-46bc-abab-ce85510aa198
---

**Expires:** when GitHub ships path/directory exclusion for Code Quality (staff: "on our
roadmap... later this year", i.e. 2026) — re-check the settings page and #186446, then
delete this file and unblock #1422.

`github-code-quality[bot]` (GitHub Advanced Security → Code Quality, distinct from CodeQL security scanning) has **no path/directory exclusion capability** as of 2026-07. Verified against GitHub docs + staff: the [Enable Code Quality settings](https://docs.github.com/en/code-security/how-tos/maintain-quality-code/enable-code-quality) expose only two knobs — language selection and runner choice — and GitHub staff (carogalvin) in [community discussion #186446](https://github.com/orgs/community/discussions/186446) say directory customization is "on our roadmap... later this year." Still public preview.

Consequences:
- It does **not** read `.github/codeql/codeql-config.yml` `paths-ignore` — that governs only the CodeQL security workflow.
- **Issue #1422** (alembic globals `revision`/`down_revision`/`branch_labels`/`depends_on` flagged as "unused") is NOT blocked on an org-admin settings action as the issue thread claimed — it's blocked on this upstream GitHub feature gap. Only levers today: wait for the roadmap feature, or disable Code Quality for Python entirely (loses real `src/` signal). Bot comments are non-gating.
- `docs/development/ci-pipeline.md` § "GitHub Code Quality vs CodeQL scoping (#1422)" and the note in `.github/codeql/codeql-config.yml` tell maintainers to "add path exclusions" in settings — that step is currently impossible. Doc needs a correction (feature not yet available).

**Re-verify before acting** — this is roadmap-dependent; GitHub may ship directory customization later in 2026, at which point the exclusion becomes applicable and #1422 unblocks. Related: [[feedback_verify_before_asserting]], [[feedback_truth_over_optimism]].
