---
name: git-mv-then-add-old-path-aborts-commit
description: "After `git mv`, passing the OLD path to a later `git add` fatals and silently aborts the ENTIRE add, committing only an empty rename. Verify staged content with --stat before committing any mv+edit."
metadata: 
  node_type: memory
  type: reference
  originSessionId: 8377e960-8e7a-4aba-8c4d-4aedb89a6629
---

After `git mv old new`, the rename is staged but the working-tree EDITS to `new` are left UNSTAGED (git mv stages the index rename using old's HEAD content, not the modified working content). If a later `git add a b OLD c` includes the now-nonexistent OLD path, git prints `fatal: pathspec '...' did not match any files` and ABORTS THE ENTIRE `git add` — staging NOTHING new. The subsequent `git commit` then ships only the git-mv-staged rename: a 100%-similarity, "0 insertions(+), 0 deletions(-)" EMPTY rename — losing the content migration AND every other file you meant to include.

**How to apply:**
1. When committing a `git mv` + content edits: `git add` only the NEW path (plus the other edited files); never the old path.
2. ALWAYS `git diff --cached --stat` before committing a mv+edit. A real mv+edit shows insertions/deletions and a sub-100% rename (e.g. "rename ... (52%)"); a bare "100% rename, 0 insertions/0 deletions" means the content + other files were NOT staged.
3. Recovery if you shipped the empty rename: `git reset --soft HEAD~1` → `git add` the NEW path (+ others) → verify `--stat` shows real +/- → recommit.

Hit on PR #1307 T4: first commit `2aa1c0356` was an empty rename (the `git add` listed the moved file's old `tests/unit/` path); recovered to `129a1dd6f` (52% rename) via reset --soft + re-add new path. Ties [[feedback_verify_before_asserting]].
