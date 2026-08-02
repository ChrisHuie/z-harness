---
name: feedback-wire-shape-change-systematic-sweep
description: "When changing wire shape, payload shape, or any cross-cutting test contract — do the full systematic sweep BEFORE pushing, not reactively per CI failure"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: acdcab63-786c-4cc7-9c58-54f2c30d2c24
---

When changing wire shape (e.g. handlers from `return dict` to `raise`), payload shape (e.g. legacy `product_ids` → `packages[]`), or any cross-cutting test contract, the WHOLE sweep happens BEFORE the first push — not one symptom per CI cycle.

**Why:** The user pushed back hard after I burned multiple CI cycles fixing tests one-at-a-time after my Item #1 wire-shape change on PR #1306. Each cycle I claimed "I'll fix this now and run the systematic sweep" but the next push surfaced more sites I'd missed. The pattern was always the same: I'd construct a test payload from memory ("video_premium" + `product_ids: [...]` + `budget: {total, currency}`) without reading the schema or the working sibling test 10 lines away.

The user said: "We are supposed to look for patterns and not address in the lazy or just guess or say something way but don't verify and systematically make sure we are addressing similar instances of the same problem? This is supposed to be systematic. Why isnt it"

**How to apply:**

Before pushing ANY commit that changes a wire shape, payload shape, error path, or test contract — do this checklist. No exceptions. No "I'll catch the rest in the next push":

1. **Read the schema first.** Open the type definition for the request/response involved (`src/core/schemas/_base.py`, `.venv/lib/python3.12/site-packages/adcp/types/.../*.py`). Confirm field names (plural vs singular), field types (str vs list, float vs Budget object), required vs optional. Never construct a test payload from memory.

2. **Find a working sibling test.** Before writing a new test payload, grep for an existing passing test calling the same endpoint. Mirror its payload-construction pattern (helper function, factory, builder) rather than re-inventing the shape.

3. **Enumerate ALL forms of the old pattern.** For each pattern affected:
   - `grep -rn '<old-assertion-form>'` across `tests/unit/`, `tests/integration/`, `tests/e2e/`, `tests/admin/`, `tests/bdd/`
   - Read each match and classify: needs-fix / legitimate-success-path / unrelated
   - Document the classification in the commit message

4. **Run the candidate fixes locally before pushing.** Use `eval $(.claude/skills/agent-db/agent-db.sh up)` + `uv run pytest` against the bare Postgres for integration; full `./run_all_tests.sh` for e2e/admin. The infrastructure is fast — pretending it isn't and pushing to CI to "see what fails" is wasted time + the user's CI minutes.

5. **Cross-PR check.** `gh pr list --state=open --json number,files` to find every other PR touching the same files. For each, `gh pr diff <num> -- <file>` to verify they're not preempting or conflicting with the same fix. Flag conflicts as part of the commit message, not after.

6. **The forbidden phrases.** Never write "Let me do the systematic sweep now" while ALREADY pushing a one-test fix. If a sweep is needed, the sweep IS the work — the fix follows the sweep, never precedes it.

7. **When CI surfaces a failing test, ask "what's the CLASS of assertion this represents?"** — not "how do I make this specific test pass?". The class is what gets enumerated; the individual test is just an instance.

8. **Wire VALUE/string changes are wire-shape changes too — and you review them by CONSUMER, not diff-scope.** A change to a wire-emitted constant (a `*_SUGGESTION`, a recovery/message text) has no structural old-form to grep, and its graders may be BASELINE: when the branch was REBASED onto an earlier PR that wired them, the grading scenarios sit OUTSIDE the PR diff, so "tests/bdd diff = conftest-only" / "no test-file diff" NEVER clears it. Grep every consumer of the field repo-wide (features/steps/integration), not just changed files. The content oracle must pin the emitted value to the spec SSOT (the pinned `error-code.json` enumMetadata), **not** to the constant the value is derived from — `assert wire == THE_CONSTANT` moves in lockstep and can never fail on a text drift (the serializer-tautology, [[feedback_claimed_invariant_needs_failing_oracle]]). Presence-only (`include "suggestion" field`) and actionable-verb steps pass regardless of the text, so they hide it. Detector: `suggestion_audit.py`; helper: `tests/helpers/pinned_spec.py`. See [[reference_per_diff_review_detectors]].

This is the same pattern as [[feedback_complete_claim_requires_full_pattern_enumeration]], [[feedback_pattern_extraction]], [[feedback_run_e2e_locally_before_push]], and [[feedback_audit_checklist_systematic]] — those memories existed and were not applied. The failure mode is treating each CI failure as a new task instead of a probe revealing a class of bug.
