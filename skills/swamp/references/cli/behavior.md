# swamp CLI: behavior
Generated from `swamp help --json`, swamp 20261030.195233.0-sha.713d92e4. Do not edit by hand; regenerate with `python3 scripts/render_cli_reference.py`.

Root commands in this group: behavior.

## swamp behavior (alias: behaviour)

Manage and run behaviors (preferred over 'model')

## swamp behavior run

```text
Execute a method on a behavior. With @type prefix, auto-creates the definition if needed.

Errors follow the --json envelope and exit codes in 'swamp --help'. Error codes this command reports (match on "code", not the message):

    lock_timeout             Another invocation holds the behavior lock (exit 75)
    datastore_v3_writer_busy Another process is writing the v3 datastore (exit 75)
    model_not_found          No behavior matches the given name
    unknown_model_type       The @type prefix does not match any installed type
    unknown_method           The behavior does not define the requested method
    no_evaluated_definition  No evaluated definition exists (use --last-evaluated)
    evaluated_cache_may_hold_secrets
                             Cached evaluation from an older swamp may hold secrets;
                             re-run without --last-evaluated
    evaluated_cache_holds_sensitive_arguments
                             Cached evaluation holds a sensitive argument that did not
                             come from a vault; --last-evaluated cannot replay it
    missing_deps             Required extension dependencies are not installed
    method_execution_failed  The method returned an error
    not_authenticated        Not signed in (run 'swamp auth login')
    cancelled                Operation was cancelled (e.g. Ctrl+C)

The lock wait defaults to 60 seconds. Set the SWAMP_LOCK_TIMEOUT_MS environment variable (milliseconds) to wait longer.
```

Arguments: behavior_or_type, method_name, definition_name?  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--last-evaluated` |  | Skip CEL evaluation, use previously evaluated definition |
| `--input` | <value:string> | Input values (key=value or JSON) |
| `--input-file` | <file:string> | Input values from YAML file (cannot combine with --stdin) |
| `--stdin` |  | Read inputs from stdin (piped data) |
| `--literal-inputs` |  | Treat input values as data: no expression evaluation, no @file reading (with --server, needs a serve that supports it) |
| `--tag` | <tag:string> | Add tag to produced data (KEY=VALUE, repeatable) |
| `--skip-check` | <name:string> | Skip a specific pre-flight check by name |
| `--skip-check-label` | <label:string> | Skip pre-flight checks with this label |
| `--skip-checks` |  | Skip all pre-flight checks |
| `--skip-reports` |  | Skip all post-run reports |
| `--skip-report` | <name:string> | Skip a specific post-run report by name |
| `--skip-report-label` | <label:string> | Skip post-run reports with this label |
| `--report` | <name:string> | Run only this report (inclusion filter) |
| `--report-label` | <label:string> | Run only reports with this label (inclusion filter) |
| `--timeout` | <duration:string> | Cancellation deadline — seconds (e.g. 30, 1800) or duration string (e.g. 30s, 5m, 1h). Cooperative — only honored by methods that check AbortSignal. |
| `--server` | <url:string> | Run through a 'swamp serve' server (ws:// or http://) instead of locally; no local repo required (env: SWAMP_SERVE_URL; in a checkout whose datastore is format 3, only this flag runs it on serve, and the env makes serve its datastore's upstream). |
| `--traceparent` | <value:string> | W3C traceparent for per-invocation trace context (env: TRACEPARENT) |
| `--tracestate` | <value:string> | W3C tracestate for per-invocation trace context (env: TRACESTATE) |

Common flags (see index.md): `--repo-dir`, `--token`, `--token-file`, `--ca-cert`

## swamp behavior create

Create a new behavior definition

Arguments: type, name  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--global-arg` | <arg:string> | Set global argument (key=value, repeatable) |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp behavior get

Show details of a behavior definition

Arguments: behavior_id_or_name  (`?` marks optional)

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp behavior edit

Edit a behavior definition file

Arguments: behavior_id_or_name?  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--allow-rename` |  | Allow a stdin update to change the behavior's name; refused otherwise |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp behavior delete

Delete a behavior and all related artifacts

Arguments: behavior_id_or_name  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `-f, --force` |  | Skip confirmation prompt (alias for --yes) and allow deletion when data artifacts exist |

Common flags (see index.md): `--repo-dir`, `-y, --yes`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp behavior validate

Validate a behavior definition against its schema

Arguments: behavior_id_or_name?  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--label` | <label:string> | Only run checks with this label |
| `--method` | <method:string> | Validate as a run of this method: its arguments, the global arguments and the checks that apply to it |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp behavior evaluate

Evaluate expressions in behavior definitions

Arguments: behavior_id_or_name?  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--all` |  | Evaluate all behavior definitions |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp behavior search (alias: list)

Search for behavior definitions

Arguments: query?  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--all` |  | Include internal behavior types |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp behavior cancel

Cancel a running method run

Arguments: behavior_id_or_name?  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--all` |  | Cancel all running method runs, skipping runs a live swamp serve owns |
| `--reason` | <reason:string> | Reason for cancellation |

Common flags (see index.md): `--repo-dir`

## swamp behavior lease

Hold behavior locks at serve across commands (team mode)

## swamp behavior lease acquire

Hold a behavior's lock at serve across commands, renewed by each command in this checkout (team mode)

Arguments: behavior_id_or_name  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--for` | <duration:string> | How long the lease is held between renewals (5s to 60m) |

Common flags (see index.md): `--repo-dir`

## swamp behavior lease release

End the lease this checkout holds on a behavior at serve

Arguments: behavior_id_or_name  (`?` marks optional)

Common flags (see index.md): `--repo-dir`

## swamp behavior lease status

List the leases this checkout holds at serve

Common flags (see index.md): `--repo-dir`

## swamp behavior describe

Describe a method on a behavior with argument details

Arguments: behavior_id_or_name, method_name  (`?` marks optional)

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp behavior history

Method run history commands

Arguments: output_id_or_behavior_name  (`?` marks optional)

Common flags (see index.md): `--repo-dir`

## swamp behavior history get

Show details of a method run

Arguments: output_id_or_behavior_name  (`?` marks optional)

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp behavior history search (alias: list)

Search method run history

Arguments: query?  (`?` marks optional)

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp behavior history logs

Show logs for a method run

Arguments: output_id_or_behavior_name  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--tail` | <lines:number> | Show only the last N lines |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp behavior output

Manage behavior outputs

Arguments: output_id_or_behavior_name  (`?` marks optional)

Common flags (see index.md): `--repo-dir`

## swamp behavior output get

Show details of a behavior output

Arguments: output_id_or_behavior_name  (`?` marks optional)

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp behavior output search (alias: list)

Search for behavior outputs

Arguments: query?  (`?` marks optional)

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp behavior output logs

Show log artifact content for a behavior output

Arguments: output_id  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--tail` | <n:number> | Show only last N lines |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp behavior output data

Show data artifact content for a behavior output

Arguments: output_id  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--field` | <name:string> | Show only a specific field from the data |
| `--name` | <name:string> | Data name to retrieve (if output has multiple artifacts) |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp behavior type

Inspect behavior types

## swamp behavior type describe (alias: get)

Describe a behavior type with schema details

Arguments: type  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--compact` |  | Output a compact digest (method names, descriptions, argument types, output spec names) |

Common flags (see index.md): `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp behavior type search (alias: list)

Search for behavior types

Arguments: query?  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--repo-dir` | <dir:string> | Repository directory (env: SWAMP_REPO_DIR; not required for type search) |

Common flags (see index.md): `--server`, `--token`, `--token-file`, `--ca-cert`
