---
name: Thorough review before implementation
description: User wants multiple rounds of deep verification using subagents before starting implementation, especially for cross-cutting changes
type: feedback
---

<!-- audit-2026-08-01 -->
> **SUPERSEDED as of 2026-08-01.** Duplicates `feedback_thoroughness_over_momentum.md`, which is kept as the canonical version. Kept for history.
> Rationale: Its only distinct content is covered by feedback_thoroughness_over_momentum (checkpoints 1-2) plus feedback_two_phase_subagent_audit (the round mechanics). Keep those two — better evidenced, with name


Before implementing cross-cutting changes (like tool migrations, renaming, etc.), do multiple rounds of deep verification with subagents. Don't rush to exit plan mode.

**Why:** User explicitly asked for re-review multiple times before approving the pre-commit to prek migration plan. They want confidence that nothing is missed, especially for changes touching many files.

**How to apply:** For any change touching >5 files or involving mechanical replacements across the codebase, do at least 2 rounds of verification: (1) initial discovery, (2) cross-check against repo standards and developer experience. Present verified findings before asking for approval.
