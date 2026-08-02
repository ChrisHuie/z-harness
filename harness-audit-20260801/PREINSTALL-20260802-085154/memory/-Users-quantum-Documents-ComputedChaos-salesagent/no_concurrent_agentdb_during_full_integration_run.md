---
name: no-concurrent-agentdb-during-full-integration-run
description: Running other pytest commands against the single agent-db Postgres DURING a background full integration run causes contention → spurious setup ERRORs + flaky failures in DB-heavy tests. Verify via a clean re-run before concluding a code regression.
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 8377e960-8e7a-4aba-8c4d-4aedb89a6629
---

The agent-db is ONE Postgres container; `integration_db` creates+drops a unique DB per test. Launching other agent-db-using pytest commands (reproductions, targeted runs) CONCURRENTLY with a background full integration run hammers it → transient connection / `CREATE DATABASE` contention → "ERROR at setup" in whatever DB-heavy tests happen to run under load, plus flaky assertion failures — none of which reproduce in isolation.

**Why:** On PR #1307, a full integration run reported 4 failed + 28 errors (clustered in DB-heavy media_buy repository/readiness tests) — WHILE I was running several concurrent reproduction pytest commands against the same agent-db. A clean re-run with NO concurrent agent-db activity → 1969 passed, 0 failed, only the 18 known creative-agent-live env errors. The 4+28 were self-inflicted contention, not a code regression.

**How to apply:**
- While a background full integration run is in flight, do NOT launch other agent-db-using pytest commands. Wait for it to finish.
- If a full run shows DB-heavy-test failures/errors that do NOT reproduce in isolation, suspect contention (was a concurrent run active?) — but VERIFY with a clean re-run; never just assume "infra/flaky" (test-integrity policy forbids rationalizing). The clean re-run is the proof.
- Do NOT pipe a full-run's output through `tail -N` — it discards the tracebacks you need to diagnose. Redirect to a file (`> /tmp/run.log 2>&1`) and grep it.

Ties [[feedback_truth_over_optimism]] and [[feedback_snowball_to_avalanche]].
