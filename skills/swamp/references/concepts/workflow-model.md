# Workflow model

## Shape

A workflow file holds jobs; a job holds steps. Top-level fields: `id` (assigned by
`swamp workflow create`), `name`, `description`, `trigger` (`schedule` cron plus `inputs`;
fires only under `swamp serve`), `tags`, `inputs` (a JSON-schema object), `jobs`, `version`,
`concurrency`, placement (`target`, `labels`, `platform`, `queueTimeout`, `affinity`),
`autoResume`, `reports` (`require`, `skip`), `vaults` (allow list). Jobs add `dependsOn` on
other jobs and `weight`. Steps add `task`, `forEach`, `dependsOn` on steps in the same job,
`weight`, `allowFailure`, `guard`, `dataOutputOverrides`, `concurrency`, and placement.
Unknown keys are rejected with a did-you-mean suggestion. Read `swamp workflow schema get`
before editing by hand.

## Task types

| `task.type` | Fields | Notes |
|---|---|---|
| `behavior` (stored as `model_method`) | `behavior` (definition) or `behaviorType` + `behaviorName` (auto-creates), `methodName`, `inputs` (record or one expression yielding a map), `globalArgs` (only with `behaviorType`) | legacy spellings `modelIdOrName`, `modelType`, `modelName` still parse |
| `workflow` | `workflowIdOrName`, `inputs` | nesting depth 10; cycles rejected; a gate in the child suspends the parent |
| `manual_approval` | `prompt` (required), `timeout` seconds | approving records a decision; resuming runs the rest |
| `assert` | `expr` (raw CEL), `message` (interpolated), `severity` low, medium, high (default high) | produces `assertResult`; `--fail-on` sets the failing threshold (default low) |
| `wait_for_signal` | `key`, `schema` (JSON-schema object for the payload), `timeout` seconds, `acceptEarly` seconds | deliver with `swamp workflow signal`; list with `swamp workflow waits` |

## Dependencies and order

Conditions: `succeeded`, `failed`, `completed`, `skipped`, `always`, and composites `and`,
`or`, `not`. `allowFailure: true` keeps the job alive; downstream `succeeded` edges do not fire
but `completed` and `always` do. Order is topological level, then `weight` ascending, then
name. Same-level nodes run in parallel, bounded by step, then job, then workflow
`concurrency`, with `SWAMP_MAX_CONCURRENT_STEPS` as a host ceiling.

## forEach and guard

`forEach: { item: x, in: "${{ expr }}" }` expands one step per element; `self.x` is the
element (for a map, an object with `key` and `value`), `self._index` the position. The item
resolves in `name`, `behavior`, `behaviorName`, `methodName`, `inputs` and `guard`. A unique
definition per iteration: `behaviorName: proc-${{ run.id }}-${{ self._index }}`.

`guard` is raw CEL evaluated before the step; truthy skips the step with reason `guarded`. It
is the idempotency mechanism and what makes recovery safe: a guarded step that already wrote
its data is skipped on re-execution.

Targets resolve at run start, except when the expression reads `data.*` or `steps.*` or the
step has a `guard`; then they resolve when the step runs.

## Statuses

| Run | Step |
|---|---|
| `pending`, `running`, `suspended`, `succeeded`, `failed`, `cancelled`, `interrupted` | `pending`, `running`, `waiting_approval`, `succeeded`, `failed`, `skipped`, `cancelled`, `unknown` |

## Suspension, approval, resume

A `manual_approval` step suspends the run. `swamp workflow approve` records the decision and
prints the resume command; `swamp workflow resume` continues. Under `swamp serve`, auto-resume
applies only to approvals made through serve, and only when the workflow allows it:
`autoResume: true`, or no declared inputs with serve started with `--auto-resume`. A local
approve never auto-resumes. Resume inputs deep-merge over the original inputs and are
persisted, so never pass a secret value; store it with `swamp vault put` and pass the key name.

## Retry, resume from a step, recover

`swamp workflow resume <wf> --run <id>` retries the failed steps of a failed run and everything
downstream, in the same run; it is not exactly-once. A rejected gate cannot be retried that
way; use `--from <gate>`. `--from` takes the template name as written in the YAML, for example
`deploy-${{ self.env }}`, never an expanded name. Steps that succeeded before the failure are
not re-run.

A crash or forced exit leaves the run `interrupted` with in-flight steps `unknown`.
`swamp workflow recover <wf> --run <id>` settles it from its checkpoint; unguarded unknown
steps need `--acknowledge-unknown`; then `swamp workflow resume`. `swamp run doctor --fix`
settles runs whose owning process is gone.

## Cancellation

`swamp workflow cancel [name] [--run <id>] [--all] [--reason]` cancels cooperatively; Ctrl+C
during `swamp workflow run` does the same. `--all` skips serve-owned runs; cancel those with
`--server` and `--run`.

## Triggers

`trigger.schedule` is cron and fires only under `swamp serve`. Overrides live in
`.swamp/serve.yaml` via `swamp workflow trigger set|get|remove`. `swamp workflow schedule
pause|resume|list` pauses the cron without editing the definition; manual and webhook runs
still run. Webhook routes are registered on serve with `--webhook`.
