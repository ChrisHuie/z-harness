verified: 2026-07-14 · sources: prompt-craft §7 (debugging), §2.10 (evidence), modes-and-composition §3 (default stance)

# Pattern: debugging

**Purpose:** locate the root cause of a defect and prove the fix.
**Default stance:** implement (find root cause, fix, prove) — also runs under **explore** for pure diagnosis ("what's causing this?" → report, touch nothing).

## Method
- Reproduce first: a failing test or command before changing anything.
- Find the root cause; do not patch the symptom.
- Require evidence — the command and its actual output — before claiming a fix.
- Preserve the failure reasoning as you go (adapt from the error), not just the fix.

## Output contract
Reproduction (command/test that fails), root-cause statement, the fix (diff), and verification: the command plus its actual passing output.

## Rubric hooks
- Is there a reproduction established before the fix?
- Is the stated cause a genuine root cause, not a symptom patch?
- Is the fix proven with real command output rather than asserted?
