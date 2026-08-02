verified: 2026-07-14 · sources: prompt-craft §7 (code review), §2.10 (self-verification), modes-and-composition §3 (default stance)

# Pattern: code-review

**Purpose:** find real defects in a diff/PR and report each with a concrete fix.
**Default stance:** review — also runs under **implement** ("review and fix the criticals" runs the findings phase in review, then transitions to implement with findings as input).

## Method
- Scope to issue classes: logic, edge cases, security, performance.
- Assign a severity to each finding: critical / warning / suggestion. Start high-severity-only, then widen.
- Make each finding = why it is wrong + a concrete fix (not just a flag).
- Embed the project's conventions so style-consistent code is not flagged (cuts false positives).
- Adversarially self-verify before finalizing; report evidence, not assertion.

## Output contract
Severity-ranked list, high-severity first. Each finding: `location (file:line)`, `severity`, `why`, `concrete fix`. Precision over recall on the first pass — no finding spam.

## Rubric hooks
- Does every finding carry both a rationale and an actionable fix?
- Are findings severity-ranked and confined to genuine issue classes?
- Precision: any false positives or style nits inflated to criticals?
