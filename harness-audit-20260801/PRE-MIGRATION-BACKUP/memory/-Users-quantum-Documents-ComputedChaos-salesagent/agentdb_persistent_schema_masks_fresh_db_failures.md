---
name: agentdb-persistent-schema-masks-fresh-db-failures
description: "The skills agent-db is PERSISTENT — it accumulates every table/migration ever applied, so integration tests that need a table PASS locally but FAIL on a fresh CI DB with UndefinedTable. A pass on agent-db is necessary but NOT sufficient; verify moved/new integration tests on a fresh DB."
metadata: 
  node_type: memory
  type: reference
  originSessionId: 8377e960-8e7a-4aba-8c4d-4aedb89a6629
---

The skills agent-db (container `agent-pg-skills`, e.g. `localhost:52959`) is **persistent across runs** — it accumulates every table and migration ever applied to it. So an integration test that requires a table (e.g. `creative_agents`) **passes against agent-db** even when a FRESH CI database wouldn't have that table provisioned.

**PR #1307 case:** two tests were moved `tests/unit` → `tests/integration` (commit `129a1dd6f`). They PASSED on my agent-db (which already had `creative_agents` from prior migrations — verified `select to_regclass('public.creative_agents')` → non-null; the 2 tests `2 passed in 0.19s`). On the reviewer's fresh `./run_all_tests.sh ci` DB they FAILED with `psycopg2.errors.UndefinedTable: relation "creative_agents" does not exist`. The table IS created by migration `33d3c9c61315_add_creative_agents_table.py` and the model exists — so this was a provisioning/reachability gap on the fresh DB, completely hidden by my persistent DB's accumulated schema.

**Why:** persistent dev DBs give false-green on schema-provisioning and migration-reachability gaps. The accumulated schema hides whether the integration suite's OWN db-setup actually creates what the test needs from scratch.

**How to apply:** whenever you MOVE a test into the integration suite, or ADD an integration test that touches a table/migration, a pass on the persistent agent-db is necessary but **NOT sufficient**. Verify on a FRESH DB — full `./run_all_tests.sh ci`, or drop/recreate the agent-db first — before claiming the test (or the PR) passes. This is the DB-layer instance of the broader trap in [[feedback_run_full_suite_before_every_push]]. Related infra gotcha: [[reference_agentdb_port_mismatch]].
