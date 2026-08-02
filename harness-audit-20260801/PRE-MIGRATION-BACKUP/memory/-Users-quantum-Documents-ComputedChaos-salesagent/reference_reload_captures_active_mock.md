---
name: reference_reload_captures_active_mock
description: "importlib.reload of a module doing `from X import Y` permanently captures whatever mock sits at X.Y — never mix tests/unit with tests/integration in one pytest process"
metadata: 
  node_type: memory
  type: reference
  originSessionId: b9324151-908f-41b4-9a0b-cdecca3d8647
  modified: 2026-07-31T11:58:11.408Z
---

`importlib.reload(mod)` re-executes `from X import Y`, so if `X.Y` is currently patched the **mock** is bound into `mod` — and it stays after teardown, because `unittest.mock` restores `X.Y` and knows nothing about the copy the reload left behind.

In salesagent this is live: `tests/unit/conftest.py` has an autouse fixture patching `src.core.database.database_session.get_db_session` for every unit test, and `tests/unit/test_scheduler_env_var_handling.py` calls `importlib.reload()` on both scheduler modules inside that window. Measured: `tests/integration/test_media_buy_status_scheduler.py` alone = 11 passed; after the polluter in the same process = **7 failed / 4 passed**, and the 4 passes are exactly the negative "status did not change" assertions — satisfied because the scheduler did nothing. So it manufactures false findings and vacuous coverage simultaneously. Intermittent under default randomisation (3 of 5 runs). `src.core.tools.media_buy_update` is also reloaded (`test_budget_guardrails.py`) but is unaffected — it does not import `get_db_session` at module level.

**How to apply:** never put `tests/unit/` and `tests/integration/` in one pytest invocation. tox keeps them in separate envs so CI is clean, and no single `make test-entity ENTITY=<x>` co-selects them (all 17 markers checked) — but a compound `ENTITY="infra or media_buy"` does, and so does any ad-hoc `pytest tests/unit/... tests/integration/...`. If integration tests fail in a mixed run, reproduce suite-alone before calling it a finding. Generalise the check: a `MagicMock` found on a `src.*` module attribute after teardown means a reload ran under a patch. Related: [[subagent_mechanism_is_a_claim]] (the first diagnosis of this was wrong), [[congratulations_masks_failures]], [[flaky_single_green_is_luck]].
