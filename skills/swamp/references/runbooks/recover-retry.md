# Runbook: recover an interrupted run, retry a failed one

Diagnose first:

```bash
swamp run history --active
swamp run doctor                      # stale or orphaned runs; --fix settles runs whose owner died
swamp workflow history get <name> --json
swamp workflow history logs <run id> --tail 200
```

Interrupted run (crash, forced exit, serve restart; status `interrupted`, steps `unknown`):

```bash
swamp workflow recover <name> --run <id> --assess-only
swamp workflow recover <name> --run <id> [--acknowledge-unknown]   # needed for unknown steps without a guard
swamp workflow resume <name> --run <id>
```

Failed run (status `failed`):

```bash
swamp workflow resume <name> --run <id>                 # re-run the failed steps and everything downstream
swamp workflow resume <name> --run <id> --from '<step template name>' [--job <job>]
```

`--from` takes the name as written in the YAML, including any `${{ self.x }}`. Steps that
succeeded before the failure do not run again; a guarded step skips itself when its data exists.
A retry is refused when a failed step is a rejected gate (use `--from <gate>`), when a step is
still pending, running, waiting or unknown, when a job failed before any step did, when a failed
step was renamed or moved, or when a step name is used in more than one job. Every refusal
names the logs command to read.

A retry is not exactly-once: a step that changed an external system and then failed runs
again, and downstream cleanup steps run again. If the workflow or a forEach collection changed
since the run, start a new run instead.

Cancel: `swamp workflow cancel <name> [--run <id>] [--reason '<text>']`; serve-owned runs need
`--server` and `--run`.
