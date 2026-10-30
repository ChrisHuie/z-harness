# swamp CLI: workflow
Generated from `swamp help --json`, swamp 20261030.195233.0-sha.713d92e4. Do not edit by hand; regenerate with `python3 scripts/render_cli_reference.py`.

Root commands in this group: workflow.

## swamp workflow

Manage workflows

## swamp workflow create

Create a new workflow

Arguments: name  (`?` marks optional)

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp workflow delete

Delete a workflow and its run history

Arguments: workflow_id_or_name  (`?` marks optional)

Common flags (see index.md): `--repo-dir`, `-y, --yes`, `-f, --force`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp workflow edit

Edit a workflow file

Arguments: workflow_id_or_name?  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--allow-rename` |  | Allow a stdin update to change the workflow's name; refused otherwise |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp workflow evaluate

Evaluate expressions in workflow definitions

Arguments: workflow_id_or_name?  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--all` |  | Evaluate all workflow definitions |
| `--input` | <value:string> | Input values (key=value or JSON) |
| `--input-file` | <file:string> | Input values from YAML file |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp workflow get

Show details of a workflow

Arguments: workflow_id_or_name  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--graph` |  | Render the workflow as a dependency graph |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp workflow history

Workflow run history commands

Arguments: workflow_id_or_name  (`?` marks optional)

Common flags (see index.md): `--repo-dir`

## swamp workflow history get

Show a specific run by ID or the latest run for a workflow

Arguments: run_id_or_workflow  (`?` marks optional)

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp workflow history search (alias: list)

Search workflow run history

Arguments: query?  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--workflow` | <name:string> | Filter by workflow name |
| `--input` | <input:string> | Filter by workflow input (KEY=VALUE), can be repeated |
| `--filter` | <expression:string> | Filter results with a CEL expression over run metadata (inputs, tags, status, timing) |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp workflow history logs

Show logs for a workflow run

Arguments: run_id_or_workflow  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--tail` | <lines:number> | Show only the last N lines |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp workflow history outputs

Show step outputs for a workflow run

Arguments: run_id_or_workflow  (`?` marks optional)

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp workflow validate

Validate a workflow against its schema

Arguments: workflow_id_or_name?  (`?` marks optional)

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp workflow search (alias: list)

Search for workflows

Arguments: query?  (`?` marks optional)

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp workflow run

Execute a workflow. Blocks until the run completes, suspends (manual approval), fails, or is cancelled. With --server, --detach returns the run ID as soon as the server has started the run.

Arguments: workflow_id_or_name  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--last-evaluated` |  | Replay the previously evaluated workflow with the inputs it was evaluated with; an --input must match them. Behavior definitions are evaluated fresh |
| `--input` | <value:string> | Input values (key=value or JSON) |
| `--input-file` | <file:string> | Input values from YAML file (cannot combine with --stdin) |
| `--stdin` |  | Read inputs from stdin (piped data) |
| `--tag` | <tag:string> | Add tag to produced data (KEY=VALUE, repeatable) |
| `--skip-reports` |  | Skip all post-run reports |
| `--skip-report` | <name:string> | Skip a specific post-run report by name |
| `--skip-report-label` | <label:string> | Skip post-run reports with this label |
| `--report` | <name:string> | Run only this report (inclusion filter) |
| `--report-label` | <label:string> | Run only reports with this label (inclusion filter) |
| `--skip-checks` |  | Skip all pre-flight checks |
| `--skip-check` | <name:string> | Skip a specific pre-flight check by name |
| `--skip-check-label` | <label:string> | Skip pre-flight checks with this label |
| `--fail-on` | <severity:string> | Minimum assert severity that fails the run (low, medium, high). Default: low (any failure). |
| `--junit` |  | Output assert results as JUnit XML instead of normal log output |
| `--out` | <file:string> | Write output to file instead of stdout (only with --junit) |
| `--timeout` | <duration:string> | Cancellation deadline — seconds (e.g. 30, 1800) or duration string (e.g. 30s, 5m, 1h). Kills in-flight subprocesses (SIGTERM) and runs cleanup steps with always/completed conditions. |
| `--server` | <url:string> | Run through a 'swamp serve' server (ws:// or http://) instead of locally; no local repo required. Required for steps with worker placement (env: SWAMP_SERVE_URL; in a checkout whose datastore is format 3, only this flag or --detach runs it on serve, and the env makes serve its datastore's upstream). |
| `--detach` |  | Return the run ID once the server has started the run, and leave it running there; requires --server. Follow it with 'swamp workflow history get <run-id>'. |
| `--traceparent` | <value:string> | W3C traceparent for per-invocation trace context (env: TRACEPARENT) |
| `--tracestate` | <value:string> | W3C tracestate for per-invocation trace context (env: TRACESTATE) |
| `--no-supersede` |  | Do not cancel matching-input suspended runs before starting |

Common flags (see index.md): `--repo-dir`, `--token`, `--token-file`, `--ca-cert`

## swamp workflow run search (alias: list)

Search workflow run history

Arguments: query?  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--since` | <duration:string> | Only runs started within duration (1h, 1d, 7d, 1w, 1mo) |
| `--status` | <status:string> | Filter by run status (pending, running, succeeded, failed) |
| `--workflow` | <name:string> | Filter by workflow name |
| `--tag` | <tag:string> | Filter by tag (KEY=VALUE), can be repeated |
| `--input` | <input:string> | Filter by workflow input (KEY=VALUE), can be repeated |
| `--limit` | <n:number> | Max results Default: 50. |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp workflow approve

Approve a manual approval step in a suspended workflow run

Arguments: workflow_id_or_name, step_name  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--reason` | <reason:string> | Reason for approval |
| `--run` | <run_id:string> | Target a specific run ID |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp workflow cancel

Cancel a running workflow run

Arguments: workflow_id_or_name?  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--run` | <run_id:string> | Target a specific run ID (required with --server) |
| `--all` |  | Cancel all running workflow runs |
| `--reason` | <reason:string> | Reason for cancellation |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp workflow reject

Reject a manual approval step in a suspended workflow run

Arguments: workflow_id_or_name, step_name  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--reason` | <reason:string> | Reason for rejection |
| `--run` | <run_id:string> | Target a specific run ID |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp workflow recover

Recover an interrupted workflow run from its last checkpoint. Resets unknown steps to pending so 'swamp workflow resume' can re-execute them.

Arguments: workflow_id_or_name  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--run` | <run_id:string> | Target a specific interrupted run ID |
| `--acknowledge-unknown` |  | Accept re-execution risk for steps without guard expressions |
| `--assess-only` |  | Show recovery assessment without modifying the run |

Common flags (see index.md): `--repo-dir`

## swamp workflow resume

Resume a suspended workflow run after approval, or retry the failed steps of a failed run named with --run (--from picks the step to retry from)

Arguments: workflow_id_or_name  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--run` | <run_id:string> | Target a specific run ID (required to retry the failed steps of a failed run) |
| `--from` | <step:string> | Select the retry step in a failed run. Without --from, resume --run retries all failed steps. |
| `--job` | <job:string> | Select the job of the --from step, as named in the workflow, when its step name is used in more than one job |
| `--input` | <value:string> | Additional input for the resumed run (key=value or JSON); merged over the original run inputs. An input the run already has cannot change; start a new run instead |
| `--input-file` | <file:string> | Additional inputs from a YAML file, held to the rules of --input (cannot combine with --stdin) |
| `--stdin` |  | Read additional inputs from stdin (piped data), held to the rules of --input |
| `--timeout` | <duration:string> | Cancellation deadline — seconds (e.g. 30, 1800) or duration string (e.g. 30s, 5m, 1h). Cooperative — only honored by methods that check AbortSignal. |
| `--traceparent` | <value:string> | W3C traceparent for per-invocation trace context (env: TRACEPARENT) |
| `--tracestate` | <value:string> | W3C tracestate for per-invocation trace context (env: TRACESTATE) |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp workflow approvals

List all workflow runs awaiting manual approval, and gates that expired

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp workflow signal

Send a JSON message to a workflow step that waits for a signal

Arguments: wait_id?  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--workflow` | <id_or_name:string> | With --key, in place of a wait ID: the workflow whose wait holds the key |
| `--key` | <key:string> | With --workflow, in place of a wait ID: the key a wait_for_signal step declares. A step that sets acceptEarly holds a signal sent before its wait opens |
| `--payload` | <json:string> | The message, as a JSON object matching the wait's schema |
| `--idempotency-key` | <key:string> | Names this signal across retries (1-128 letters, digits, '.', ':', '-', '_'): one sent again with the same key after it was received is answered with the first, and is not delivered or held twice |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp workflow waits

List all workflow steps waiting for a signal

| Flag | Value | Description |
|---|---|---|
| `--pending` |  | Also list signals sent by key that are held for the next wait of their key |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp workflow schema

Workflow schema commands

## swamp workflow schema get

Get the schema for workflow files

Common flags (see index.md): `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp workflow trigger

Manage workflow trigger overrides in serve.yaml

## swamp workflow trigger set

Set a trigger override for a workflow in serve.yaml

Arguments: workflow_name  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--schedule` | <cron:string> | Cron expression for the trigger schedule |
| `--input` | <value:string> | Input values (key=value, repeatable; JSON syntax not supported) |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp workflow trigger get

Show the effective trigger for a workflow (built-in + override)

Arguments: workflow_name  (`?` marks optional)

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp workflow trigger remove

Remove a trigger override for a workflow from serve.yaml

Arguments: workflow_name  (`?` marks optional)

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp workflow schedule

Pause, resume and list workflow schedules without editing workflow definitions

## swamp workflow schedule pause

Pause a workflow's schedule without editing its definition; manual and webhook runs still run

Arguments: workflow_id_or_name  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--reason` | <text:string> | Why the schedule is paused; shown in list and logged at each skipped fire |
| `--until` | <time:string> | Resume automatically: a duration (30m, 2h, 1d, 1w) or an ISO-8601 time with Z or an offset |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp workflow schedule resume

Resume a paused workflow schedule (to continue a suspended run, use 'swamp workflow resume')

Arguments: workflow_id_or_name  (`?` marks optional)

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp workflow schedule list

List scheduled workflows with their cron, next fire and pause state

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`
