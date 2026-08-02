---
name: feedback-pattern-extraction
description: "After fixing PR feedback, audit the codebase for the same pattern everywhere — fix every instance, not just the cited one. PROACTIVE corollary: when YOU extract a helper or add a convention, migrate the COMPLETE sibling set AND converge every existing producer in the SAME PR — a partial extraction (some sites migrated, two conventions coexisting) is a fresh DRY violation, worse than none (PR #1307)."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: acdcab63-786c-4cc7-9c58-54f2c30d2c24
---

When fixing review feedback, the work is NOT "fix the cited site." It is
"identify the pattern, audit the codebase, fix every instance."

**TRIGGER — do this BEFORE editing the cited site, every time:** the cited line
is one of N. FIRST run a whole-repo grep / AST-scan for the pattern; classify
hits (exclude helper definitions and transport wrappers — don't over-count;
don't stop at the cited site — don't under-count); migrate ALL. Do not say
"addressed" until the grep shows zero remaining — paste the evidence. If the
pattern is AST-detectable, **the guard is the deliverable** (it enumerates every
site and stays red until done), not the single migration.

**This rule existing has NOT been enough on its own** — it was detailed and
correct and still got violated (a helper extraction migrated one function and
left a byte-identical sibling in the same file). Recall ≠ enforcement. When a
pattern recurs, escalate it to a mechanical guard — see
[[feedback_escalate_recurring_lessons_to_guards]].

**Why:** Reviewers cite ONE site to illustrate an anti-pattern. The disease
exists elsewhere. PR #1276 shipped 5+ rounds of feedback because each round
caught additional instances of patterns flagged in earlier rounds — DRY
violations, weak typing, hand-rolled identities, vacuous tests. Each
"compound" round was preventable by extracting the pattern from the first
instance and applying it broadly.

**How to apply: after EACH review feedback item:**

1. Fix the cited site (the literal request).
2. Identify the underlying pattern (what's the rule being violated?).
3. Grep / AST-scan the codebase for the same pattern at other sites.
4. Fix every instance in the SAME commit as the cited fix.
5. If the pattern is AST-detectable, propose a structural guard test
   (see CLAUDE.md "Structural Guards" — there are 24+ existing examples).
6. If the pattern is documented in CLAUDE.md, link the fix to that section.
   If not, propose a CLAUDE.md addition.

**Concrete examples of pattern extraction:**

- "Fix hand-rolled `ResolvedIdentity` at `test_X.py:39`" → audit ALL test
  files for `ResolvedIdentity(` constructions; migrate to
  `PrincipalFactory.make_identity()`. PR #1276 had 7 such sites; only the
  cited one was fixed initially.
- "Type `product: Any` as `Product | None`" → audit `src/` for `: Any`
  parameters on functions accessing typed attributes; tighten.
- "Fix `or all(...)` short-circuit at line 157" → audit `tests/` for
  `or all(` / `or any(` / broad string-match patterns.
- "Helper duplicated in 2 files" → audit related sister files (create vs
  update, get vs list) for same-pattern duplication.
- "Wire format inconsistent between create + update" → audit ALL paired
  paths for same-rule duplication; extract shared helper.

**When to skip the audit:** never. If the pattern is truly singular, the
audit confirms it in 30 seconds. If the audit finds nothing, document
"audited, no other sites found" in the commit message so reviewers know
it was checked.

**Decision tree for what to do with found instances:**

- **Same commit if straightforward** (mechanical migration, ≤10 sites)
- **Separate follow-up PR** if the audit reveals a large pattern (≥20
  sites) and migrating all in-PR would balloon scope. In that case, file
  a tracked follow-up issue and link from the current PR.
- **Structural guard** if AST-detectable — prevents recurrence beyond
  the current PR.

Pair with [[pr-review-audit-workflow]] — the workflow tells you how to
find all feedback; this discipline tells you what to do with each item.
