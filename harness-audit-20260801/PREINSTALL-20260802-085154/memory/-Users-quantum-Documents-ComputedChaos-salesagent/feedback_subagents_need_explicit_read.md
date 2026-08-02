---
name: feedback-subagents-need-explicit-read
description: "Citing memory rule filenames in subagent prompts isn't enough. Subagents skip Read unless told explicitly. Always include \"Read these files FIRST\" as Step 0."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: acdcab63-786c-4cc7-9c58-54f2c30d2c24
---

When dispatching a subagent on this project, citing memory rule filenames in the prompt **does NOT cause the subagent to read them**. They proceed without the rules, producing work that contains subtle pattern violations the parent agent would have caught.

**Concrete demonstration on PR #1306 audit-fix sweep (2026-05-27):**

- Subagent #1 (no explicit Read): produced work that contained "(audit S2)" tag in production code, "audit B1/S2 migration" labels in 6 test docstrings, hand-rolled `ResolvedIdentity(...)` instead of `PrincipalFactory.make_identity()`, and kept "PR #1306" references in xfail reasons — all violations of memory rules I cited by filename but did not tell it to read.

- Subagent #2 (explicit "MANDATORY FIRST STEP: Read these N files BEFORE doing anything else"): caught all of subagent #1's violations.

**How to apply:**

```
STEP 0 — MANDATORY: Read these memory rules FIRST (don't skip)

Use the Read tool on each in this order BEFORE writing any code:

1. /Users/quantum/.claude/projects/-Users-quantum-Documents-ComputedChaos-salesagent/memory/<rule-1>.md
2. /Users/quantum/.claude/projects/-Users-quantum-Documents-ComputedChaos-salesagent/memory/<rule-2>.md
...
```

Use the *full absolute path*. The Step 0 framing + the explicit Read instruction is what makes the subagent treat them as binding context.

**What to include:**

For any code-modifying subagent, the minimum read-list is:
- `feedback_no_issue_refs_in_comments.md`
- `feedback_no_pointless_comments.md`
- `feedback_no_internal_dialogue_in_public_artifacts.md`
- `feedback_substrate_prs_need_production_callers.md`
- `feedback_atomic_breaking_changes.md`
- `feedback_pattern_extraction.md`
- `feedback_truth_over_optimism.md`
- `feedback_verify_before_asserting.md`

Plus task-specific ones (`wire_envelope_policy.md`, `feedback_mock_only_tests_dont_prove_wiring.md`, etc.).

Related: [[feedback_subagent_model_inherit]] (no model pins — inherit session model), [[feedback_detecting_subagent_overconfidence]] (verify subagent claims with direct file inspection).
