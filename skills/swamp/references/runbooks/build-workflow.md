# Runbook: build and run a workflow

1. `swamp workflow schema get --json` and read it; unknown keys are rejected at load time.
2. `swamp workflow create <name> --json`; edit the scaffold at the returned path. Keep the
   assigned `id`.
3. Author steps per references/concepts/workflow-model.md. Fan out with `forEach`; make each
   step idempotent with a `guard` that reads the data the step writes; put an `assert` step
   after data-producing steps; pin report selection under `reports` when a report matters.
4. `swamp workflow validate <name>`; fix every line it reports.
5. `swamp workflow evaluate <name> --input k=v` to see the resolved expressions without
   executing; `swamp workflow get <name> --graph` to check the DAG shape.
6. Run: `swamp workflow run <name> --input k=v [--tag k=v] [--fail-on medium] [--junit --out results.xml]`.
   For list or object inputs pass JSON: `--input 'ids=[1,2,3]'`. The command blocks until the
   run ends or suspends; the exit code is the outcome.
7. Inspect: `swamp workflow history get <name> --json` (step statuses, `assertResult`),
   `swamp workflow history logs <run id> --tail 100`, `swamp workflow history outputs <run id>`,
   `swamp data list --workflow <name>`.
8. Schedule only under serve: add `trigger.schedule`, or `swamp workflow trigger set <name>
   --schedule '<cron>'`; `swamp workflow schedule list` shows the next fire.

Do not: write the YAML from scratch, invent an `id`, pass a secret value as an input, or run
before `validate` passes.
