---
name: feedback_review_tooling_prs_derive_invariant_and_probe_inputs
description: "For dev-tooling/CLI PRs, derive the tool's cardinal invariant and adversarially probe its inputs — the pattern-catalog reviewers miss the tool's own failure modes"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: d9f80fc4-30d4-4335-b74f-397720e30dd4
  modified: 2026-07-23T11:15:25.024Z
---

The PR-review approach is strong at "does this diff violate a known pattern?" and "is the invariant the PR *claims* actually pinned (mutation-test it)?" It is comparatively weak at "what invariant *should* this thing guarantee that no one wrote down, and what inputs break it?" On a dev-tooling / CLI / script PR, the specialist reviewers are catalog- and guard-oriented and will confirm the tests pass + patterns are clean and still miss the tool's own failure modes.

**Why:** on a re-review of a "which BDD scenarios never run" checker, the pattern reviewers verified all prior feedback was addressed with load-bearing oracles — but the findings that actually mattered came from two moves they don't systematically run: (1) stating the tool's **cardinal invariant** ("never emit a false all-clear") and hunting every path that violates it — which surfaced an env-var/ANSI false-all-clear (`FORCE_COLOR` → the XFAIL prefix regex matches nothing → "no dormant scenarios") and an incomplete-vocabulary misclassification; and (2) **adversarial input enumeration** (hostile paths, param-ids embedding the reason separator, shallow clones, `-OO` stripping docstrings) — treating the tool as an artifact to break. A strong human reviewer led with exactly these; the catalog pass would have stopped at "prior items addressed, ship."

**How to apply:** before pattern-matching a tooling/CLI PR, write down the tool's one cardinal invariant, then adversarially enumerate the inputs that break it — empty/crash subprocess output, color/locale/env vars leaking into an inherited env, hostile or renamed paths, incomplete vocabularies/enums, unusual interpreter flags. Run the tool end-to-end on a real input, not just its unit tests (its unit tests mock the environment-bound layer that is exactly where these bugs live). Also: a "prove-a-known-reason-stays-coupled" guard (AST scan for the *known* fragments) does NOT enforce "every case is classified" — the invariant is the completeness, so the oracle must assert the completeness, not a sample (see [[feedback_claimed_invariant_needs_failing_oracle]]).

Escalated (per [[feedback_escalate_to_guards]]): the pattern recurred on a second tooling re-review (the catalog specialists again did not lead with input-fuzzing; the probe had to be seeded), so it is now an ENFORCED step, not just this memory — `full-review.md` Step 4 carries a **"Tooling-PR mode"** mandate that fires when the diff's deliverable is detection/enforcement (`scripts/`, a CLI, a new checker/guard, a CI gate): state the cardinal invariant, adversarially enumerate the inputs/env that defeat it, and RUN the tool end-to-end under each (not just its env-mocking unit tests). Still unbuilt: the self-referential-oracle detector (mechanizes the "test proves the classifier agrees with itself" class). Related: [[feedback_claimed_invariant_needs_failing_oracle]], [[feedback_root_cause_first]], [[feedback_trace_flows_not_claims]], [[reference_harness_freshness_mechanisms]].
