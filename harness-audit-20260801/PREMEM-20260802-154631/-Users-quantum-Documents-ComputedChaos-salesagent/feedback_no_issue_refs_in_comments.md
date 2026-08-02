---
name: No issue/PR references in code comments
description: Do not embed issue numbers (#1057) or PR references in code comments — use self-documenting code and let git history provide traceability
type: feedback
---

Do not add issue numbers, PR numbers, or ticket references in code comments (e.g., `# Fix for #1057`).

**Why:** Code comments should explain *why* the code works the way it does, not link to external tracking systems. Git blame and PR descriptions provide that traceability. Issue refs in comments are noise that becomes stale.

**How to apply:** Write comments that describe the intent/behavior. The commit message and PR title reference the issue — the code itself should stand on its own.
