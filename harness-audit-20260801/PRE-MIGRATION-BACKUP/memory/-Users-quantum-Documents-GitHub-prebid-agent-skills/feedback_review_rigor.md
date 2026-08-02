---
name: Review rigor — steelman before asserting
description: When reviewing PRs/code/designs on this project, steelman the implementor first, verify each finding against full surrounding context, and never assert as fact what's only verified from an excerpt
type: feedback
originSessionId: 7b9e64c9-de1e-4baa-afc8-54801c7bc543
---

<!-- audit-2026-08-01 -->
> **SUPERSEDED as of 2026-08-01.** Duplicates `/Users/quantum/.claude/projects/-Users-quantum-Documents-ComputedChaos-salesagent/memory/feedback_verify_before_asserting.md`, which is kept as the canonical version. Kept for history.
> Rationale: Core rule (never assert unverified) is stated better by the HIGH-trust twin and is already in ~/.claude/CLAUDE.md's Evidence section. Names the /review skill, so flagged harness_critical.

When reviewing implementor work on this project (PR reviews, design audits, code reads), do not state findings as fact until each one has been:

1. **Steelmanned**: ask "what could justify this?" Read the surrounding paragraphs, ADRs, design notes, sibling files, and commit messages — not just the line cited. Assume the implementor knows things I don't.
2. **Re-verified against the full context**: an excerpt is not the file. A claim that "X is missing" must be checked across the entire repo (the file may exist under a different name; the rule may be encoded in a sibling YAML; the constraint may live in a schema $ref).
3. **Checked for explicit prior decision**: scan for ADRs, "Notable design decisions", "Risks", "Out of scope", and execution-plan audit-correction tables (e.g., the R1–R11 corrections) that may already address the concern.

**Why:** Colleagues lose trust when reviewers raise findings the implementor already addressed in a paragraph the reviewer skipped. The cost of the reviewer doing 30s more verification is far lower than the cost of the implementor having to research and explain. "I read your X but you may want to clarify Y" is acceptable; "X is wrong" is not, unless verified end-to-end.

**How to apply:** Before posting any finding ranked HIGH or BLOCKING:
- Re-read the full file, not just the line range
- Search the repo for related docs/ADRs/audit corrections
- For docs claiming alignment with upstream, read the upstream artifact directly (don't trust the cited claim)
- If the finding still stands, frame as "I verified X by Y; the issue is Z" not "X is wrong"
- If the finding is ambiguous, frame as a question, not a defect

Applies to PR-review synthesis, /review skill output, ad-hoc code reads, and design-doc audits.
