---
name: feedback-verify-before-asserting
description: "Never state a fix, cause, or scope as fact without verifying. Separate observed from inferred; read the actual code; check pre-existing vs introduced"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: acdcab63-786c-4cc7-9c58-54f2c30d2c24
---

Never state a fix, root cause, or scope claim as fact without verifying it directly. The user has called this out repeatedly — they are tired of pattern of confident wrong claims.

**Why:** Across one session I made the same mistake at least four times:
1. Constructed an e2e test payload (`product_ids` plural, `budget` as object) from memory instead of reading the `PackageRequest` schema 10 lines below in the same file. The sibling working test showed the correct shape — I never opened it.
2. Asserted "envelope-level `adcp_error` key" was correct for Principal-not-found, when the established pattern (verified later via sister test in `test_media_buy.py`) is the impl returns CreateMediaBuyError variant.
3. Claimed `the reviewer's #1274 asks have 5 of 8 partial/unverified` when actually reading the code showed ALL 8 done.
4. Proposed "fix MCP `get_products` signature to add `adcp_major_version`" without checking — it's a SEPARATE field from `adcp_version` (which #1274 added), it's a pre-existing gap tracked in `issue #1247`, the storyboard CI is non-required (`continue-on-error: true`), and the fix is out of scope for #1274.

The user said: "How is it a thing that you say things only to find out they are wrong. Don't fucking tell me wrong things because you are lazy or dumb or don't have it in context or on the model. Do the god damn research. I am tired of this shit!!"

**How to apply:**

Before stating ANY of the following as fact:
- "This is the fix for X" — read the code at the exact line cited, verify the change makes sense, verify it's not already done
- "X is broken because Y" — verify Y by inspection, not by pattern-matching against similar issues
- "X is out of scope" — verify by reading the PR's actual diff and the issue tracker
- "X is in scope" — same; check what files the PR touches before claiming a fix belongs to it
- "X is a pre-existing issue" — verify by checking main, not by assumption
- "All N of the reviewer's asks are addressed" — verify each one by reading the code matching the ask, not by pattern-matching the commit message

The check is: can I cite a specific file:line that proves the claim? If yes, state it with the citation. If no, label it as inference ("looks like" / "probably" / "need to verify") and do the verification before acting on it.

**Specific protocol for PR audits:**

1. For each reviewer ask: read the exact file + function the ask references; verify the change is present in the current branch (not just commit messages); cite file:line in the audit output
2. For each CI failure: read the actual failure log (not just the test name); identify the exact assertion that failed; check if the fix exists on main (via `git show origin/main:<file>`); only then claim "resolves on rebase"
3. For each proposed fix: confirm the file referenced still has the bug (not just based on grep snapshots); confirm the fix isn't already present in a similar form
4. For "this is out of scope": verify by checking the PR's diff vs main, AND by checking for an existing issue/tracker entry

**Forbidden behaviors:**
- Stating a fix without having opened the file at the cited line
- Saying "the bug is X" based on the error text alone without verifying the source line
- Inferring scope from PR title or branch name instead of from the diff
- Repeating a claim ("we already verified Y") without re-checking it

**Scope-of-verification — the trap of narrow checks:**

When the user asks "verify before push" or you offer verification as an option, the verification scope must match the CLAIM scope, not just the bugs you already know about. Concrete trap from this session: I offered "Run the 7 previously-failing tests locally" as the Recommended verification on a merge commit. The user picked it. I ran the 7 tests, they passed, I reported "ready". Then push surfaced:
- 1 NEW unit-test failure (`if_wholesale_feed_version` — yet more schema drift, would have shown in a full unit run)
- An entire BDD failure class (`KeyError: 'principal'` — the merge added BDD to the required gates; would have shown in `tox -e bdd`)

The verification was narrowly chosen because narrow was what I expected to break. That is the exact failure mode this memory was supposed to prevent — biasing verification toward the bugs I already had hypotheses for, instead of the actual change-blast-radius.

**Rule:** for a merge or rebase or wire-shape change, the verification floor is `make quality` AT MINIMUM (unit + lint + format + typecheck) — not "the specific tests I think will be affected". For changes that touch BDD step files or test harnesses, add `tox -e bdd`. For wire-shape or transport-boundary changes, add `tox -e e2e` against a real Docker stack. The shortcut of "just run what I expect to fail" reliably misses everything I didn't predict.

If offering verification options to the user, the "Recommended" one defaults to the BROADER scope, not the narrowest. The narrower options are for follow-up, not first pass.

**Pattern-level gate (absorbs verify_memory_and_code_before_claiming_pattern_addressed, 2026-06-11):**

Before asserting a pattern/decision is addressed / considered / redundant / done / N-A:
- RE-READ the governing memory FILE (don't cite from recall), AND verify it against CURRENT code: signatures, gate ordering, ORM vs Pydantic schema attrs, transport body shapes. Memories drift — an 11-day-old wire-envelope memory listed a `check_backward_compat` kwarg the live `assert_envelope_shape` didn't have; citing it would have passed an invalid kwarg.
- "Redundant / covered / can't be done / already handled" is a CONCLUSION that needs the same evidence as "it's a bug": read the code, run the test. Two of the biggest finds in one session came from RUNNING tests argued to be redundant (a genuinely-needed A2A update-path wire guard; a pre-existing REST/MCP/A2A body-shape asymmetry). Running the test is proof; reasoning about whether it's needed is not.
- When editing wire/error/transport code, read the WHOLE file, not just the diff hunk.

Related: [[feedback_root_cause_first]], [[feedback_thorough_review]], [[feedback_wire_shape_change_systematic_sweep]], [[feedback_complete_claim_requires_full_pattern_enumeration]], [[feedback_run_e2e_locally_before_push]]. Those memories existed and were not applied. This memory exists to make the rule sharper: **no factual claim without a citation that I have actually verified in the moment, not from memory** — AND the verification must cover the claim's scope, not just the bugs I expected.
