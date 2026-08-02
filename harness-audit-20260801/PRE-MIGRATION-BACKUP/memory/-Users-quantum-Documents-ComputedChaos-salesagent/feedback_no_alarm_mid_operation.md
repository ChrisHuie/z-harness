---
name: no-alarm-mid-operation
description: "Never raise alarmist claims (\"reverted\", \"lost\", \"broken\", \"missing\") about file/repo state during an in-flight git or hook operation — wait for it to finish and check the FINAL state"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: acdcab63-786c-4cc7-9c58-54f2c30d2c24
---

**The rule:** When a git/hook/build operation is in flight, file state is in a TRANSIENT state that doesn't reflect the final outcome. Never make claims like "my edits got reverted" / "the file is missing X" / "something broke my work" while such an operation is mid-run. Wait for it to fully finish, then read the FINAL state, then describe what happened.

**Why:** This is a specific failure mode that's bitten the user multiple times in one session — me making panicked, alarmist, energetic-but-wrong claims based on transient state. Specific case:

- Pre-commit hooks **stash unstaged changes** during their run (`Restored changes from /Users/quantum/.cache/pre-commit/patch...`). While stashed, files temporarily revert to HEAD content. If I `grep` or `Read` during the stash window, I see OLD content.
- I saw OLD content at line 891 of `src/core/tools/products.py` mid-stash and wrote a multi-paragraph panic narrative about "edits got reverted" / "something undid my work" — when actually the edits were merely temporarily stashed.
- After pre-commit finished, the stash was automatically restored and my edits came back. **No data was ever at risk.**

**How to apply:**

1. **If a background git/build/hook operation is running, do NOT inspect file state to describe it.** Wait for completion (notification + output file shows final result).
2. **If you see "missing" / "old" / "reverted" content in a file you just edited:**
   - First check: is there an in-flight git/pre-commit operation? (`git status` shows what's staging-vs-working)
   - First check: was a pre-commit hook run recently? (`ls -lt /Users/quantum/.cache/pre-commit/patch*`)
   - If yes: wait for it to finish before making any claims. The state is transient.
3. **Banned alarm phrases mid-operation:** "got reverted", "edits are gone", "something undid", "files broken", "data lost", "panicking", "weird".
4. **Replace with:** "operation X is mid-flight; deferring observation until completion." Then continue once the operation is done.
5. **After it finishes** — if state genuinely shows missing edits, THEN investigate. But almost always, the state is restored by the hook's own cleanup.

**Corollary to [[feedback_verify_before_asserting]] and [[feedback_truth_over_optimism]]:** verification must be done at a STABLE state, not during transient operations. "I just edited X" is true; "X was reverted" requires post-stable-state confirmation.

**Pattern recognition signal:** if I'm about to write a multi-paragraph explanation of "what went wrong" while a tool is still running, STOP and wait first. The panic narrative is almost always wrong.
