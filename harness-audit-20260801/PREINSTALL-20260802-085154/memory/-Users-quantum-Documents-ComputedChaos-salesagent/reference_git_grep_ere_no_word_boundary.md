---
name: reference_git_grep_ere_no_word_boundary
description: "git grep -E (POSIX ERE) silently ignores \\b word boundaries → false \"empty\" results; use -P (PCRE)"
metadata: 
  node_type: memory
  type: reference
  originSessionId: ca7615c0-66eb-4da7-9d44-4c43bc372723
---

`git grep -E` (POSIX ERE) does NOT honor `\b` as a word boundary — it matches nothing rather than erroring, so a pattern like `\bProperty\(` returns EMPTY even when `Property(` is all over the tree. Use `-P` (PCRE): `git grep -P "\bProperty\("`.

Observed cost: a review subagent used `git grep -E "\b<name>\(|..."` to prove a symbol had "no runtime use," concluded a `# noqa` was unnecessary, and flagged an existing memory as "drifted." The grep was silently broken; the symbol was constructed in 10+ sites and the noqa was load-bearing. Re-running with `-P` (and checking the multi-line `from pkg import (\n  Name,\n)` form, which single-line `from .* import .*Name` also misses) settled it.

**How to apply:** A subagent's "not found / empty grep" is a hypothesis to falsify, not a fact ([[feedback_detecting_subagent_overconfidence]], [[feedback_guard_matcher_completeness]]). Before acting on it, re-run the search yourself with a matcher that models every form — `-P` for `\b`/lookarounds, and account for multi-line parenthesized imports. Prefer `ast-grep` for call-shape matching so string/comment hits don't pollute counts.
