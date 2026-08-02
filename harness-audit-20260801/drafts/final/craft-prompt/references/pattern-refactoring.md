verified: 2026-07-14 · sources: prompt-craft §7 (refactoring), §2.1 (success criteria), modes-and-composition §3 (default stance)

# Pattern: refactoring

**Purpose:** improve structure while preserving behavior exactly.
**Default stance:** implement — also runs under **plan** for large or architectural refactors (decide the shape first).

## Method
- Hold a behavior-preserving contract: tests stay green throughout.
- Enumerate explicitly what must NOT change (public API, outputs, side effects).
- Make small, reversible diffs; verify at each step, not only at the end.
- State the success criteria and let the path stay flexible; do not over-prescribe steps.

## Output contract
The invariant (what must not change) stated up front, the stepwise diffs, and green-test evidence at each step or at completion.

## Rubric hooks
- Do tests stay green (behavior demonstrably preserved)?
- Are the "must not change" items enumerated and honored?
- Are diffs small, reversible, and verified incrementally?
