---
name: feedback_fanout_preflight_disk_and_docker
description: "Check free disk and that Docker is already up BEFORE dispatching a multi-agent fan-out; a full data volume masquerades as unrelated errors, and cycling Docker mid-fan-out stalls agents polling for it."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: d15e20da-0c34-4049-87cf-159a68530a4b
  modified: 2026-07-29T23:12:34.888Z
---

Run this before any multi-agent dispatch, not after the first agent reports something odd:

```bash
df -h /System/Volumes/Data | tail -1      # macOS: `df -h /` shows the SEALED system volume, not the data volume
docker info --format '{{.ServerVersion}}'  # must already be UP if any agent needs a DB
du -sh ~/Library/Containers/com.docker.docker/Data 2>/dev/null
```

**Why — a full data volume does not look like a full disk.** At 100% the Bash tool cannot create its own output file, so *every* command fails with `ENOSPC` on a path unrelated to the command; pytest fails earlier and more misleadingly with `FileNotFoundError: No usable temporary directory found` (workaround: `export TMPDIR=<scratchpad>`); and the Docker daemon simply stops answering, hanging past a 180s timeout. Observed cost: four of six dispatched reviewers died mid-run. The dangerous part is that **a mutation-testing agent running under ENOSPC emits false failures indistinguishable from real findings** — an infra failure is neither a pass nor a failure, so the correct response is to stop and reclaim, never to interpret the redness.

Reclaim order: `uv cache prune` is safe (removes unused entries only). Docker's VM disk image is usually the dominant consumer and deleting it destroys all local images/containers/volumes — that is the user's call, not a reviewer's, and the harness's own permission layer may block the recursive delete anyway.

**Never cycle Docker during a fan-out.** Agents instructed to poll for Docker observe a restart as contention and stall; one explicitly reported that "another agent appears to be cycling Docker" when the culprit was the orchestrator. Bring infra up, verify it, *then* dispatch; if it must be restarted, stop the agents first.

**Scope the dispatch to the infra that exists.** With no DB, dispatch only the dimensions needing none and state in each prompt which assignments are deferred — otherwise agents burn budget rediscovering the blocker, or infer an integration verdict from a unit run. Related: [[no_concurrent_agentdb_during_full_integration_run]], [[reference_agentdb_port_mismatch]], [[docker_desktop_stale_singleton_after_crash]], [[feedback_no_agent_fanout_by_default]], [[feedback_isolate_mutation_testing_reviewers_in_worktrees]].
