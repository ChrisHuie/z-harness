---
name: feedback-merge-creates-duplication-sweep-ssot
description: Merging main into a long-lived branch can CREATE duplication — main grows an SSOT helper for a shape the branch hand-rolled. Post-merge reconciliation must sweep branch-authored helpers against helpers the merge brought in.
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f2e0a5cd-a513-47b6-a919-ef16c0c2431d
  modified: 2026-07-31T04:08:27.040Z
---

Merging origin/main into a long-lived feature branch can create DRY violations
that neither side had at author time: the branch hand-rolls a small helper
(legitimately — no SSOT existed), main independently grows the SSOT, and the
merge unites both. No conflict fires because the files differ; the duplication
ratchet (pylint R0801) can't see it because the implementations are textually
different one-liners.

**Why:** PR #1389 hand-rolled `identifier_type_str()` on 06-10 when no
`enum_value` existed anywhere in the tree. PR #1399 (SDK upgrade) landed
`src/core/enum_helpers.enum_value` on main ~06-16; our 06-17 merge brought it
in. Four more main-merges and two dedicated SSOT-hygiene passes (marker SSOT,
ext-namespace SSOT) never noticed, because those passes swept only the
patterns the reviewer had already named. The reviewer caught it a month later
— plus the hand-rolled helper carried an unverified defensive rationale
("can arrive as a bare string after some deserialization paths") that
empirically could not happen (only `model_construct` bypasses the enum, and
nothing constructs Identifiers that way), violating
[[feedback_verify_before_asserting]].

**How to apply:** After every merge of main into a long-lived branch, add this
to the reconciliation checklist alongside conflicts/tests/allowlists:

1. List helpers the merge brought in:
   `git diff --name-only <pre-merge>..origin/main -- 'src/core/*helper*' 'src/core/*util*' 'src/services/'`
   plus skim new `def`s in shared modules:
   `git diff <pre-merge>..origin/main -- src/ | grep '^+def \|^+    def '`
2. For each new shared helper, grep the BRANCH-authored code (files this
   branch added/edited) for hand-rolled equivalents of the shape it
   centralizes — match on the idiom (e.g. `hasattr(x, "value")`,
   `.value if isinstance`), not the helper's name.
3. Converge immediately: adopt the SSOT or delete the local copy. If the local
   copy exists because the type is statically known, prefer direct access and
   fail loud (No Quiet Failures) over importing the duck-typed helper.

The reverse direction also applies: helpers the BRANCH created may now have
main-side duplicates — sweep both ways.

**Sharpest variant — a REBASE can resurrect the exact line the PR moved, so the
PR's own fix becomes the dead copy while its comment still asserts the fix.**
A PR whose whole point was relocating a statement (write-after-auth instead of
write-before-auth) gets rebased onto a main that grew an unrelated change around
the ORIGINAL position. Git sees main's line as context and the PR's line as an
addition, and keeps BOTH. Now the pre-fix behaviour is live, the post-fix line is
a no-op, and the invariant comment sitting beside the dead line reads as
satisfied. Neither a conflict nor CI nor the duplication ratchet fires.

Detection is a one-liner, and it is the thing to run on any rebase of a
relocation PR — count the statement per revision rather than reading the diff:
`for r in <main> <pre-rebase-head> <post-rebase-head> <HEAD>; do
  echo -n "$r: "; git show "${r}:path/to/file" | grep -c 'the exact statement'; done`
(Use `${r}:` with braces — bare `$r:src/...` triggers zsh's `:s` modifier and
git reports a bogus "ambiguous argument".) A count that goes 1 → 1 → 2 is the
tell. Then check WHICH copy the PR added: if the addition is the post-fix
position, the fix is dead, not the duplicate.

Related: [[feedback_duplicate_deletion_needs_reader_enumeration]] (deleting the
resurrected copy is NOT automatically safe), [[feedback_claimed_invariant_needs_failing_oracle]]
(the comment asserting the invariant is what makes this survive review).

Related: [[feedback_pattern_extraction]] (sweep after a fix — this is the
merge-triggered variant), [[feedback_semantic_ssot_defect_class]] (the
duplication class structural guards can't see).
