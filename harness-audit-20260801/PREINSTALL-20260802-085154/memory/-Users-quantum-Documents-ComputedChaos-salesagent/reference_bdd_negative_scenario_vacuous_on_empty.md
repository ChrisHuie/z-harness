---
name: reference_bdd_negative_scenario_vacuous_on_empty
description: "BDD \"counter/violated\" isolation steps that assert only set-emptiness pass vacuously on an empty response; pair with a non-empty anchor"
metadata: 
  node_type: memory
  type: reference
  originSessionId: bfdaad74-228a-442c-b9a0-1fb3ad484dba
---

A BDD negative/counter step whose only assertion is a set-intersection emptiness check —
`leaked = returned_ids & other_principal_ids; assert not leaked` — passes VACUOUSLY when the
response is empty (`set() & X == set()`). Reachable whenever the query legitimately returns
`[]` (e.g. auth resolves the wrong/absent principal, seed not committed, over-restrictive
filter). The `_wire_creatives` loud guard only catches a *missing* wire (errored transport), not
an empty-but-successful one.

**How to apply:** a counter step ("none of B's creatives visible") must also assert the response
is non-empty — mirror the sibling "holds" step's `assert returned, "…empty…"`. The paired holds
scenario usually compensates at the suite level, and the canonical drop-the-`principal_id`-filter
mutation reddens the counter non-vacuously (it ADDS rows), so this is robustness hardening, not a
correctness bug — but the counter alone is one-directional without the anchor. Seen in
`tests/bdd/test_uc018_list_creatives.py::then_none_belong_to` (PR #1551); found independently by
4 review lenses. Note: UC-018 defines steps INLINE in the scenario module, so the BDD
assertion-strength guards (which scan `tests/bdd/steps/` only) never see them — see
[[reference_bdd_inline_steps_escape_guards]]. Related: [[feedback_claimed_invariant_needs_failing_oracle]], [[reference_bdd_harness_pitfalls]].
