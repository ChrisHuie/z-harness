verified: 2026-07-14 · sources: prompt-craft §7 (test generation), §2 (positive instructions), modes-and-composition §3 (default stance)

# Pattern: test-generation

**Purpose:** generate tests that genuinely catch regressions.
**Default stance:** implement — also runs under **explore** to propose/enumerate candidate cases before writing them.

## Method
- Use TDD framing: write the tests, confirm they FAIL first, then make them pass.
- Explicitly hunt edge cases (boundaries, empty/null, ISO-week, leap-second) — models surface cases humans miss; ask for them.
- Validate the generated tests; never trust them untested.
- One behavior per test, with a clear name stating that behavior.

## Output contract
The tests; a confirmed red→green transition (failing before the implementation, passing after); the enumerated edge cases covered.

## Rubric hooks
- Were the tests confirmed to fail before the code made them pass?
- Do they cover non-obvious edge cases, not just the happy path?
- Are the generated tests themselves validated rather than blindly trusted?
