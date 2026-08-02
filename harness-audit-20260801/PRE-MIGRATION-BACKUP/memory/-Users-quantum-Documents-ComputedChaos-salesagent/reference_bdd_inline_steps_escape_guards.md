---
name: reference_bdd_inline_steps_escape_guards
description: BDD steps defined inline in a test_ucNNN_*.py scenario module (not tests/bdd/steps/) are invisible to every BDD structural guard
metadata: 
  node_type: memory
  type: reference
  originSessionId: bfdaad74-228a-442c-b9a0-1fb3ad484dba
---

The BDD assertion-strength / silent-env / duplicate-step / dict-registry guards
(`tests/unit/test_architecture_bdd_*.py` + `_bdd_guard_helpers.iter_then_functions`) anchor their
scan on `tests/bdd/steps/` only. UC-018 (`tests/bdd/test_uc018_list_creatives.py`) is the sole UC
that defines its @given/@when/@then INLINE in the scenario-binding module (deliberately — the
shared phrasings would alter UC-004/005/006 if registered globally via `pytest_plugins`). Net
effect: those inline steps are verified by ZERO structural guard — `iter_then_functions()` returns
0 Then-steps from that file (verified PR #1551, N=8 guards enumerated). A green guard suite reads
as "caught everything" but structurally cannot see this file (scan-set escape, P39).

**How to apply:** when reviewing UC-018 (or any future root-level `test_ucNNN_*.py` with inline
steps), apply the guard matchers to the AST by hand — the guards won't. Durable fix (follow-up, not
any single PR's job): widen the BDD guard scan root to also include `tests/bdd/*.py`, or relocate
UC-018 steps to `tests/bdd/steps/domain/uc018_list_creatives.py`. Related:
[[reference_bdd_negative_scenario_vacuous_on_empty]], [[feedback_structural_guards_pin_production_paths]], [[feedback_guard_matcher_completeness]].
