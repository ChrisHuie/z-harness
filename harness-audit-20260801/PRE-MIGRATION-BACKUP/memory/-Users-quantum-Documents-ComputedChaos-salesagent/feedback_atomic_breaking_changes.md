---
name: feedback-atomic-breaking-changes
description: "Type narrowings + schema changes + renames must land atomically with their fixture/caller updates. Always cite origin head, not local head, when claiming \"ready\""
metadata: 
  node_type: memory
  type: feedback
  originSessionId: acdcab63-786c-4cc7-9c58-54f2c30d2c24
---

When introducing a constraint that breaks existing usage (type narrowing like `str` → `Literal`, `Any` → concrete type, `Optional[X]` → `X`; schema field add; API rename), the constraint change AND every caller/fixture update needed to satisfy the new constraint MUST land together. Either:

1. **Preferred:** Single commit covering the constraint + every site that needs the fix.
2. **Acceptable with explicit warning:** Sequential commits with a loud "push these together — pushing only #1 breaks CI" call-out.

**Why:** Concrete miss on PR #1273. I committed `test_mode: str` → `Literal[...]` as commit A, then noticed existing test fixtures used `"stress"` (which the new Literal rejects), fixed them in commit B. Commit A reached origin alone (whether via my `--no-verify` or the user, doesn't matter — the split is the problem). CI immediately broke on the existing test fixtures because A's constraint rejects them, and B was sitting unpushed on my local. The user asked "what happened?" because I had said "ready for push" when origin was in a broken intermediate state.

**How to apply:**

1. **Before splitting a breaking change into multiple commits**, ask: "Can CI pass on just the first commit?" If no — squash, or label the dependency loud.

2. **When claiming "ready", always cite the origin head, not the local head.** Bad: "22/22 tests pass locally, ready to push." Good: "Origin currently has only A which breaks CI — local has B which fixes it. Push both together OR push as one squashed commit; do NOT push A alone."

3. **`git log @{u}..HEAD` is mandatory before any "ready" claim.** If non-empty, name each unpushed commit AND any commit-A-vs-commit-B dependency. The user can't see your local state.

4. **Grep for ALL usages of the changed constraint before committing the constraint.** If the change is `str` → `Literal["a", "b", "c"]`, grep for every site that used to pass an arbitrary string. Update them in the same commit as the type change. Cross-codebase grep + atomic fix beats "I'll see what fails."

5. **Type narrowings are the highest-risk class.** `str` → `Literal` breaks everything that was outside the narrowed set. `Any` → `ConcreteType` surfaces every implicit-contract violation. `Optional[X]` → `X` breaks every `None` call site. These all require the cross-codebase grep + atomic fix discipline; never push the type change alone.

6. **Multiple unpushed commits with dependencies need an explicit push-order spec.** If commits must land in a specific order, say so. If they can be squashed, do that.

This is distinct from [[feedback_verify_before_asserting]] (which is about *what* to verify) and [[feedback_wire_shape_change_systematic_sweep]] (which is about pre-push grep enumeration). This memory is about *atomicity* — even when you've verified locally and grep'd the codebase, splitting the *push order* breaks CI for everyone watching. And [[feedback_user_owns_git_push]] means the user is the one who feels that breakage first — communicate origin vs local state plainly so they don't push a broken intermediate.
