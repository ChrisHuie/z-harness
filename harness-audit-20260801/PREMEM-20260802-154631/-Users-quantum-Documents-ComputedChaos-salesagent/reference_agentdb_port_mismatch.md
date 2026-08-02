---
name: reference-agentdb-port-mismatch
description: "RESOLVED: agent-db.sh now allocates its port dynamically (find_port scans 50000-60000, port stored in state file + DATABASE_URL). Durable diagnostic: an integration-test wall of 'Connection refused' ERRORs = infra (env port vs real container port), not test failures — check `docker ps` before owning failures."
metadata: 
  node_type: memory
  type: reference
  originSessionId: eea6a61f-fb14-405a-8a08-b5c73900ce1c
---

**STATUS: RESOLVED — verified 2026-06-11 by reading `.claude/skills/agent-db/agent-db.sh`** (`find_port()` scans 50000-60000; the chosen port is embedded in DATABASE_URL and persisted to the worktree's state file; each worktree gets its own `agent-pg-<id>` container). The historical bug — script exporting a hardcoded `:50000` while the real container listened elsewhere — cannot recur in this form.

**Durable diagnostic (keep):** when an integration run produces a WALL of identical `connection refused` ERRORs (every test, conftest retrying 12×), that is INFRA, not test failures — and not passes either (the tests never ran). Don't rationalize it; diagnose it:
- `docker ps --format '{{.Names}}\t{{.Ports}}' | grep agent-pg` — the real published port.
- Compare against `echo $DATABASE_URL` / the state file. A stale `eval` from a previous container generation can still desync the env; re-run `eval $(.claude/skills/agent-db/agent-db.sh up)` to refresh.
- With the right port the same files pass in seconds (historically: 21 passed in 6.4s vs 638s of all-ERROR retries on the wrong port).

`timeout` is not installed on this macOS — don't wrap test commands in it.

Related: [[agentdb_persistent_schema_masks_fresh_db_failures]] (the reuse trap that DOES survive), [[no_concurrent_agentdb_during_full_integration_run]], [[feedback_run_full_suite_before_every_push]].
