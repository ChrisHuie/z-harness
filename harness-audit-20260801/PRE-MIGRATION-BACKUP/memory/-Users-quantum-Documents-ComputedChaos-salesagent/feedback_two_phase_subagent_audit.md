---
name: feedback-two-phase-subagent-audit
description: "For high-stakes subagent work (substrate PRs, multi-fix sweeps), run a second-pass audit subagent (explicit memory Read; inherits session model) to catch pattern violations the first subagent introduced. Repeatedly catches real issues."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: acdcab63-786c-4cc7-9c58-54f2c30d2c24
---

When a subagent does substantial code-modifying work (multi-fix sweeps, audit-driven refactors, merge resolutions), **always run a second-pass audit subagent before pushing**. The second-pass agent gets explicit memory-rule Read instructions and audits the first agent's output.

**Why:** Subagents lack the parent's accumulated memory context. Even when prompted carefully, they introduce subtle pattern violations (internal-narrative comments, hand-rolled identities, PR-narrative labels in committed artifacts) that a memory-aware audit catches.

**Concrete win on PR #1306 audit fix (2026-05-27):**

- Phase 1 subagent (no explicit memory read): landed 5 commits addressing 4 BLOCKERs + 8 SHOULD-FIX. Work was substantively good.
- Phase 2 subagent (explicit Read of 17 memory files): found 2 BLOCKERs + 5 SHOULD-FIX in Phase 1's output (the load-bearing variable was the explicit memory Read + fresh audit context, not the model class):
  - "(audit S2)" tag in production code
  - "audit B1/S2 migration" labels in 6 test docstrings
  - Hand-rolled `ResolvedIdentity(...)` instead of `PrincipalFactory.make_identity()`
  - 9 stale "PR #1306 / review / Post-B4 / Post-R3" references in test docstrings
  - Missing UNSUPPORTED_FEATURE wire test
  - Plus 3 NITs

All of these violated existing memory rules. None would have been caught by `make quality` or CI.

**Pattern:**

```python
# Phase 1: do the work
Agent({
  description: "Fix list X",
  subagent_type: "general-purpose",
  # no model: — inherit session model (feedback_subagent_model_inherit)
  isolation: "worktree",
  prompt: "<work prompt with citations to memory>"
})

# Phase 2: audit Phase 1's output
Agent({
  description: "Memory-driven QA on Phase 1 output",
  subagent_type: "general-purpose",
  prompt: """
    STEP 0 — MANDATORY: Read these memory rules FIRST (don't skip)
    1. /Users/quantum/.claude/projects/.../memory/feedback_no_issue_refs_in_comments.md
    2. /Users/quantum/.claude/projects/.../memory/feedback_no_pointless_comments.md
    3. /Users/quantum/.claude/projects/.../memory/feedback_no_internal_dialogue_in_public_artifacts.md
    ...

    Then audit commits <SHA1>..<SHA2> for violations of each rule.
    Cite file:line for every finding.
    Do NOT modify code — report only.
  """
})

# Phase 3: parent agent applies fixes from Phase 2's findings
```

**Cost:** ~10-15 min extra per major subagent run. Worth it for substrate PRs and any work going to public review by a high-bar reviewer.

**Don't use for:** Single-file fixes, trivial refactors, exploratory research. Two-phase is for code-modifying sweeps that touch ≥3 production files.

Related: [[feedback_subagents_need_explicit_read]] (Phase 2 always uses explicit Read), [[feedback_subagent_model_inherit]] (no model pins — inherit session), [[feedback_detecting_subagent_overconfidence]] (Phase 2 verifies Phase 1's claims).
