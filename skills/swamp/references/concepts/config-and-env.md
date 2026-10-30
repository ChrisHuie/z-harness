# Configuration, environment, exit codes

## Layering

CLI flags, then `SWAMP_*` environment variables, then user config (`swamp config get|set|list`:
`update.auto`, `update.cadence`, `telemetry.collection`, `workspaces.dir`), then `.swamp.yaml`,
then defaults.

## Account

Every command needs a swamp-club.com sign-in except `help`, `version`, `completions`,
`update`, `auth *` and `start`. Interactive: `swamp auth login`. Headless (CI, agents):
`SWAMP_API_KEY` or `SWAMP_API_KEY_FILE`; a collective token carries scopes such as
`extensions:push`, `serve:*`, `datastore:*`, `vault:*`, `oauth:manage`. `swamp auth whoami`
shows the identity, the club URL and the effective serve URL.

## Exit codes and the error envelope

| Exit | Meaning |
|---|---|
| 0 | success |
| 1 | error |
| 2 | unknown command or subcommand, or too many arguments |
| 75 | temporary failure such as lock contention or a temporary sign-in block; retry with backoff |
| 130 | interrupted |

With `--json` (or `SWAMP_CLI_OUTPUT_JSON=1`) a failing command writes one JSON document to
stderr: `{ "error": "<message>", "code": "<error_code>" }`. Match on `code`; message text can
change between releases. `swamp behavior run` codes: `lock_timeout` and
`datastore_v3_writer_busy` (exit 75), `model_not_found`, `unknown_model_type`,
`unknown_method`, `no_evaluated_definition`, `evaluated_cache_may_hold_secrets`,
`evaluated_cache_holds_sensitive_arguments`, `missing_deps`, `method_execution_failed`,
`not_authenticated`, `cancelled`.

## `.swamp.yaml` keys

`swampVersion`, `initializedAt`, `upgradedAt`, `repoId`, `tools` (list; legacy `tool`),
`gitignoreManaged`, `logLevel`, `telemetryDisabled`, `telemetryEndpoint`,
`telemetryKeepFlushed`, `autoGc`, `garbageCollection` (block, see
references/concepts/data-retention.md), `defaultVault`, `serverAddress`, directory overrides
`modelsDir`, `workflowsDir`, `vaultsDir`, `datastoresDir`, `reportsDir`, `trustedCollectives`,
`trustMemberCollectives`, `datastore` (`type`, `path`, `bucket`, `prefix`, `region`,
`endpoint`, `forcePathStyle`, `config`, `namespace`, `managedConfig`).

Repository resolution: `--repo-dir`, then `SWAMP_REPO_DIR`, then an upward walk from the
working directory for `.swamp.yaml`, bounded by the git root or ten levels.

## Environment variables by role

| Role | Variables |
|---|---|
| Account | `SWAMP_API_KEY`, `SWAMP_API_KEY_FILE`, `SWAMP_SIGNIN_TOKEN`, `SWAMP_CLUB_URL` |
| Repo and paths | `SWAMP_REPO_DIR`, `SWAMP_EXTENSIONS_DIR`, `SWAMP_BEHAVIORS_DIR` or `SWAMP_MODELS_DIR`, `SWAMP_WORKFLOWS_DIR`, `SWAMP_VAULTS_DIR`, `SWAMP_DATASTORES_DIR`, `SWAMP_REPORTS_DIR`, `SWAMP_HOME`, `SWAMP_CONFIG_DIR` |
| Serve client | `SWAMP_SERVE_URL` or `SWAMP_SERVER_URL`, `SWAMP_SERVER_TOKEN`, `SWAMP_SERVER_TOKEN_FILE`, `SWAMP_CA_CERT`, `SWAMP_SERVE_EXTRA_HEADERS` |
| Serve server | `SWAMP_SERVE_ADDRESS`, `SWAMP_SERVE_ADVERTISE_ADDRESS`, `SWAMP_SERVE_CERT_FILE`, `SWAMP_SERVE_KEY_FILE`, `SWAMP_GRANTS_FILE`, `SWAMP_GRANTS_DIR`, `SWAMP_AUTO_RESUME`, `SWAMP_DASHBOARD`, `SWAMP_REMOTE_ONLY`, `SWAMP_TRUSTED_HOSTS`, `SWAMP_QUEUE_TIMEOUT`, `SWAMP_DISPATCH_ENV_ALLOW`, `SWAMP_MAX_CONCURRENT_RUNS`, `SWAMP_MAX_RUN_DURATION` and the interval settings listed in references/cli/serve.md |
| Workers | `SWAMP_WORKER_TOKEN`, `SWAMP_WORKER_TOKEN_FILE`, `SWAMP_WORKER_LABELS`, `SWAMP_WORKER_CACHE_DIR`, `SWAMP_WORKER_CONCURRENCY`, `SWAMP_WORKER_MAX_DISPATCHES`, `SWAMP_WORKER_IDLE_TIMEOUT` |
| Execution | `SWAMP_LOCK_TIMEOUT_MS`, `SWAMP_MAX_CONCURRENT_STEPS`, `SWAMP_EPHEMERAL_BUDGET`, `SWAMP_DATASTORE_SYNC_TIMEOUT_MS`, `TRACEPARENT`, `TRACESTATE` |
| Output and noise | `SWAMP_CLI_OUTPUT_JSON`, `SWAMP_LOG_LEVEL`, `SWAMP_NO_TELEMETRY`, `SWAMP_TELEMETRY_ENDPOINT`, `SWAMP_NO_INBOX_NOTICE`, `SWAMP_NO_UPDATE_CHECK` |
| Inside shell methods | `__SWAMP_IN_N` (data values), `__SWAMP_VAULT_N` (secrets) |

Telemetry opt-outs combine: any one of `--no-telemetry`, `SWAMP_NO_TELEMETRY`,
`telemetry.collection`, or `telemetryDisabled` disables it.
