# swamp CLI: serve
Generated from `swamp help --json`, swamp 20261030.195233.0-sha.713d92e4. Do not edit by hand; regenerate with `python3 scripts/render_cli_reference.py`.

Root commands in this group: serve.

## swamp serve

```text
Start a WebSocket API server for workflow and behavior execution.

Service deployments: swamp loads all extensions — including already-pulled repo extensions — through an embedded runtime under the swamp data directory (SWAMP_HOME, or ~/.swamp). `swamp serve daemon enable` sets SWAMP_HOME and SWAMP_CONFIG_DIR in the generated service unit automatically. If you author a service unit manually, set SWAMP_HOME or HOME in the unit environment, e.g. `Environment=SWAMP_HOME=/opt/swamp`. Without it, scheduled workflow runs fail with "Unknown behavior type" for pulled extension types. SWAMP_HOME also moves the config directory, where `swamp auth login` stores credentials, to $SWAMP_HOME/config; for --auth-mode token or oauth, also set SWAMP_CONFIG_DIR to the config directory holding those credentials (~/.config/swamp by default).
```

| Flag | Value | Description |
|---|---|---|
| `--config` | <path:string> | Path to serve config file (default: .swamp/serve.yaml; a relative path resolves against the repository) |
| `--port` | <port:number> | Port to listen on Default: 9090. |
| `--host` | <host:string> | Host to bind to Default: 127.0.0.1. |
| `--address` | <url:string> | The address clients reach this serve at, as they put it in serverAddress. Required to write a v3 datastore 'swamp datastore claim' gave to that address (env: SWAMP_SERVE_ADDRESS) |
| `--advertise-address` | <url:string> | This node's own http(s) address, as the other serve nodes sharing its v3 datastore reach it. Followers forward writes to the leader at this address; without it a node bound to a wildcard or loopback host cannot be forwarded to (env: SWAMP_SERVE_ADVERTISE_ADDRESS) |
| `--ca-cert` | <path:string> | PEM file of CA certificates to trust, besides the system store, when this node forwards to its team's leader (a relative path resolves against the repository) (env: SWAMP_CA_CERT) |
| `--no-schedule` |  | Disable scheduled workflow execution |
| `--cert-file` | <path:string> | Path to PEM-encoded TLS certificate (env: SWAMP_SERVE_CERT_FILE; a relative path resolves against the repository) |
| `--key-file` | <path:string> | Path to PEM-encoded TLS private key (env: SWAMP_SERVE_KEY_FILE; a relative path resolves against the repository) |
| `--grants-file` | <path:string> | Path to an external grants YAML file loaded at startup (a relative path resolves against the repository); its grants are stored with source file:grants-file (env: SWAMP_GRANTS_FILE) |
| `--grants-dir` | <path:string> | Path to an additional directory of grants YAML files, read alongside the repository grants/ directory (a relative path resolves against the repository); their grants are stored with source file:grants-dir/<filename> (env: SWAMP_GRANTS_DIR) |
| `--grant-reload` | <mode:string> | Policy snapshot reload mode: manual (default) or auto Default: manual. |
| `--webhook` | <spec:string> | Register a webhook endpoint: <route>:<workflow>:<secret>[:<scheme>[:<header>[:<prefix>]]]. scheme is one of github (default), jira, linear, stripe, slack, generic, or a webhook extension type (@collective/name); generic requires a header name and accepts an optional value prefix. Secret may use @env=VAR to read from an environment variable, @file=/path to read from a file, or @vault=<vault>:<key> to read from a configured vault (avoids secrets in argv) |
| `--auth-mode` | <mode:string> | Authentication mode: none (default, deprecated), token, or oauth Default: none. |
| `--admins` | <principals:string> | Comma-separated admin principals: plain usernames for OAuth mode (e.g. dmc), user:<subject-id> for token mode |
| `--allowed-collectives` | <list:string> | Comma-separated collective slugs for OAuth admission policy |
| `--allowed-users` | <list:string> | Comma-separated swamp-club usernames or user:<sub> subjects for OAuth admission policy |
| `--oauth-provider` | <url:string> | OAuth authorization server URL (default: https://swamp-club.com) |
| `--oauth-client-id` | <id:string> | OAuth client ID — auto-registered on first start if omitted. Set SWAMP_API_KEY, SWAMP_API_KEY_FILE or --club-api-key-file (a collective API token with oauth:manage scope) for headless registration without browser interaction. |
| `--club-api-key-file` | <path:string> | Path to a file containing the collective API key (oauth:manage scope) used for headless OAuth registration, username lookup, instance registration and heartbeat; overrides SWAMP_API_KEY_FILE and SWAMP_API_KEY |
| `--oauth-client-name` | <name:string> | OAuth client name used during registration (env: SWAMP_OAUTH_CLIENT_NAME). Defaults to swamp-serve-{repoName}-{hostname}. |
| `--groups-field` | <field:string> | Userinfo field name for group/collective memberships (default: collectives) |
| `--restricted-model-types` | <types:string> | Comma-separated behavior types whose behaviors only admins may create, run, edit or delete, along with their data and the workflow steps that run them (e.g. command/shell,@acme/deploy); a leading @ is ignored when matching, so @acme/deploy and acme/deploy are the same entry. Requires --auth-mode token or oauth |
| `--restricted-commands` | <cmds:string> | Comma-separated server commands that require admin authority (e.g. datastore.namespace.list,extension.install); names match exactly. Requires --auth-mode token or oauth |
| `--approve-requires-explicit-grant` |  | Require a grant that names approve to decide a manual approval gate; a run grant alone no longer implies approve. Off by default. Requires --auth-mode token or oauth (env: SWAMP_APPROVE_REQUIRES_EXPLICIT_GRANT) |
| `--signal-requires-explicit-grant` |  | Require a grant that names signal to deliver a signal to a workflow's wait; a run grant alone no longer implies signal. Off by default. Requires --auth-mode token or oauth (env: SWAMP_SIGNAL_REQUIRES_EXPLICIT_GRANT) |
| `--tag-requires-explicit-grant` |  | Require a grant that names tag to change a behavior's or workflow's tags; a write grant alone no longer implies tag. Off by default. Requires --auth-mode token or oauth (env: SWAMP_TAG_REQUIRES_EXPLICIT_GRANT) |
| `--group-refresh-interval` | <duration:string> | How often to re-fetch IdP group memberships for active server tokens (env: SWAMP_GROUP_REFRESH_INTERVAL). Accepts seconds (14400), explicit units (4h, 30m), or 0 to disable. Default: 4h. Requires --auth-mode oauth. |
| `--trust-proxy` |  | Trust X-Forwarded-For header for client IP in token auth rate limiting (enable when behind a reverse proxy) |
| `--ws-idle-timeout` | <duration:string> | WebSocket idle timeout — how long the server waits for a pong before closing the connection (env: SWAMP_WS_IDLE_TIMEOUT). Accepts seconds (30), explicit units (2m, 5m), or 0 to disable. Default: 30s |
| `--queue-timeout` | <duration:string> | How long a placed step queues for a matching worker before timing out (env: SWAMP_QUEUE_TIMEOUT). Accepts seconds (60), explicit units (2m, 10m), or 0 to disable. Default: 10m |
| `--verify-on-enroll` |  | Run a fleet probe on each enrolling worker before it becomes schedulable — workers that fail are marked unverified (env: SWAMP_VERIFY_ON_ENROLL) |
| `--trusted-hosts` | <hosts:string> | Comma-separated hostnames or host:port authorities to trust for Host and browser Origin validation when binding off-loopback or serving through a reverse proxy; give a public address on a port other than 443 as host:port (e.g. host.docker.internal,host.minikube.internal). Preserves the DNS rebinding defense while allowing Docker/Kubernetes worker connections (env: SWAMP_TRUSTED_HOSTS) |
| `--dispatch-env-allow` | <names:string> | Comma-separated environment variable names; only these ship to workers with each dispatch (case-insensitive, never HOME, PATH, SWAMP_* or the other denylisted names). Unset ships serve's whole environment minus the denylist. To ship none, set 'dispatch-env-allow: []' in serve.yaml or an empty SWAMP_DISPATCH_ENV_ALLOW (env: SWAMP_DISPATCH_ENV_ALLOW) |
| `--detach-runs` |  | Deprecated — HA mode is now detected automatically based on your datastore configuration. This flag is accepted for backwards compatibility but has no effect. |
| `--heartbeat-interval` | <duration:string> | How often to write an instance heartbeat to the control-plane store. Accepts seconds (30), explicit units (30s, 1m). Default: 30s. Only effective with a control-plane-capable datastore (env: SWAMP_HEARTBEAT_INTERVAL) |
| `--stale-ttl` | <duration:string> | How long a heartbeat can go without update before the instance is considered dead. Must be at least 2x --heartbeat-interval (values below this are rejected). Accepts seconds (90), explicit units (90s, 2m). Default: 90s. Only effective with a control-plane-capable datastore (env: SWAMP_STALE_TTL) |
| `--reconciliation-interval` | <duration:string> | How often to scan for dead peer instances and reconcile their orphaned runs. Accepts seconds (60), explicit units (60s, 2m). Default: 60s. Only effective with a control-plane-capable datastore (env: SWAMP_RECONCILIATION_INTERVAL) |
| `--hydration-timeout` | <duration:string> | Maximum time to wait for initial datastore cache hydration at startup. Accepts seconds (60), explicit units (60s, 5m). Default: 60s. Increase for large repos where the initial pull takes longer. With managedConfig it applies to each of 3 attempts, and startup fails if all of them fail (env: SWAMP_HYDRATION_TIMEOUT) |
| `--shutdown-drain-timeout` | <duration:string> | How long shutdown (SIGTERM/SIGINT) waits for in-flight webhook, scheduled and API runs to finish before aborting them. Accepts seconds (30), explicit units (30s, 5m), or 0 to abort at once. Default: 30s. Keep it below the pod's terminationGracePeriodSeconds minus about 25s (env: SWAMP_SHUTDOWN_DRAIN_TIMEOUT) |
| `--datastore-poll-interval` | <duration:string> | How often to pull config, access data and runtime data from the remote datastore, and to check the managedConfig extension lockfile for changes. Accepts seconds (30), explicit units (30s, 1m). Default: 30s. Minimum: 1s. Only effective with a remote datastore or managedConfig (env: SWAMP_DATASTORE_POLL_INTERVAL) |
| `--continuation-sweep-interval` | <duration:string> | How often to look for suspended runs that need no further decision and continue them, when their workflow's auto-resume policy allows. Accepts seconds (30), explicit units (30s, 1m). Default: 30s. 0 disables (env: SWAMP_CONTINUATION_SWEEP_INTERVAL) |
| `--max-signal-wait-timeout` | <duration:string> | The longest timeout a wait_for_signal step may ask for on this server. A step that asks for more fails when it would start waiting; a wait already open keeps its deadline. Accepts seconds (3600), explicit units (1h, 7d). Default and upper limit: 1y (env: SWAMP_MAX_SIGNAL_WAIT_TIMEOUT) |
| `--token-gc-interval` | <duration:string> | How often to delete revoked server tokens, and expired ones past the grace period. Accepts seconds (3600), explicit units (30s, 1h). Default: 1h. 0 disables (env: SWAMP_TOKEN_GC_INTERVAL) |
| `--token-gc-grace-period` | <duration:string> | How long an expired server token is kept before the token GC deletes it. Accepts seconds (3600), explicit units (30s, 1h). Default: 1h. 0 deletes at expiry (env: SWAMP_TOKEN_GC_GRACE_PERIOD) |
| `--max-concurrent-runs` | <count:integer> | Maximum number of concurrent detached runs across all principals. Default: 100. (env: SWAMP_MAX_CONCURRENT_RUNS) |
| `--max-concurrent-scheduled-runs` | <count:integer> | Maximum number of scheduled workflow runs in flight at once. Different workflows run together up to this limit; a workflow never overlaps itself. Separate from --max-concurrent-runs. Default: 1. (env: SWAMP_MAX_CONCURRENT_SCHEDULED_RUNS) |
| `--max-concurrent-webhook-runs` | <count:integer> | Maximum number of webhook workflow runs in flight at once, across all routes; deliveries to the same route may overlap. Separate from --max-concurrent-runs. Default: 1. (env: SWAMP_MAX_CONCURRENT_WEBHOOK_RUNS) |
| `--max-runs-per-principal` | <count:integer> | Maximum number of concurrent detached runs per authenticated principal. Unset by default (no per-principal limit). (env: SWAMP_MAX_RUNS_PER_PRINCIPAL) |
| `--max-run-duration` | <duration:string> | Maximum wall-clock time a run may execute before being aborted. Accepts seconds (3600), explicit units (1h, 30m). Unset by default (no limit). (env: SWAMP_MAX_RUN_DURATION) |
| `--hot-reload` |  | Enable SIGHUP-based hot-reload for pulled extension bundles and trigger overrides from serve.yaml. Writes a PID file to .swamp/serve.pid; use 'swamp serve reload' to trigger a reload |
| `--enable-internal-api` |  | Enable the /internal/runs endpoint for full run history access (env: SWAMP_ENABLE_INTERNAL_API) |
| `--remote-only` |  | Disable local (loopback) execution — all steps must declare placement and be dispatched to remote workers. Steps without placement will error (env: SWAMP_REMOTE_ONLY) |
| `--dashboard` |  | Enable the web dashboard at /dashboard (env: SWAMP_DASHBOARD) |
| `--auto-resume` |  | Resume a suspended run once every approval gate on it is decided and every wait for a signal is settled. Applies to workflows that declare no inputs; a workflow with inputs must set autoResume: true itself, and autoResume: false opts out (env: SWAMP_AUTO_RESUME) |

Common flags (see index.md): `--repo-dir`

## swamp serve reload

```text
Reload pulled extension bundles and refresh the trust list on a running serve process.

With --server, sends a reload request to the running server over WebSocket. Without --server, reads .swamp/serve.pid and sends SIGHUP locally. Requires the serve process to be running with --hot-reload.
```

| Flag | Value | Description |
|---|---|---|
| `--server` | <url:string> | Reload extensions on a 'swamp serve' server instead of locally (env: SWAMP_SERVE_URL) |

Common flags (see index.md): `--repo-dir`, `--token`, `--token-file`, `--ca-cert`

## swamp serve check-config

```text
Check a serve config's auth settings and token secrets key without starting the server.

Loads the auth settings the same way 'swamp serve' does (flags, env vars, then the config file), validates them, and in oauth mode looks up every admin and allowed-user name on the OAuth provider. Exits non-zero if a name is unknown or serve would refuse to start. Uses --club-api-key-file, SWAMP_API_KEY_FILE, SWAMP_API_KEY or your 'swamp auth login' credential, and only sends it to the provider that issued it (set SWAMP_CLUB_URL for a custom provider). With a token-secrets block, also reads the token secrets key from its vault and checks it is a usable 32-byte key, without printing it. It also reads the grant files serve reads (grants/, --grants-file and --grants-dir) and fails if serve would refuse them; grant type spellings that match no type as written are warnings, and stored grants are reported by serve at startup. A restricted-model-types entry without a leading '@' that is not a built-in type is a warning, since extension types are not loaded here: write an extension type with its '@'. Apart from a --grants-file or --grants-dir outside the repository, it reads only this repository's files and never contacts the datastore, so it cannot tell whether a control plane was already moved to a key (or to a different key), and vaults whose configs arrive through the datastore must be synced first; serve checks both at startup. Nothing is written to the vault. Nothing is written to the repository either, except that checking a token-secrets key loads vault extensions, which can create or refresh swamp's extension catalog (.swamp/_extension_catalog.db) and, when the vault's type is not installed, install its extension.
```

| Flag | Value | Description |
|---|---|---|
| `--config` | <path:string> | Path to serve config file (default: .swamp/serve.yaml; a relative path resolves against the repository) |
| `--auth-mode` | <mode:string> | Authentication mode to check, as passed to 'swamp serve' (overrides the config file) |
| `--admins` | <principals:string> | Comma-separated admin usernames, as passed to 'swamp serve' (overrides the config file) |
| `--allowed-users` | <list:string> | Comma-separated allowed-user usernames, as passed to 'swamp serve' (overrides the config file) |
| `--allowed-collectives` | <list:string> | Comma-separated collective slugs, as passed to 'swamp serve' (overrides the config file) |
| `--oauth-provider` | <url:string> | OAuth provider URL, as passed to 'swamp serve' (overrides the config file) |
| `--grants-file` | <path:string> | External grants YAML file to check, as passed to 'swamp serve' (overrides the config file; env: SWAMP_GRANTS_FILE) |
| `--grants-dir` | <path:string> | Directory of grants YAML files to check, as passed to 'swamp serve' (overrides the config file; env: SWAMP_GRANTS_DIR) |
| `--club-api-key-file` | <path:string> | Path to a file containing the collective API key used to look up usernames; overrides SWAMP_API_KEY_FILE and SWAMP_API_KEY |

Common flags (see index.md): `--repo-dir`

## swamp serve daemon

Manage swamp serve as a system daemon (EXPERIMENTAL)

## swamp serve daemon enable

Enable swamp serve as a system daemon (launchd/systemd)

| Flag | Value | Description |
|---|---|---|
| `--user` |  | Install as a per-user service (systemd --user / launchd agent) |
| `--config` | <path:string> | Path to serve config file (default: .swamp/serve.yaml; a relative path resolves against the repository) |
| `--port` | <port:number> | Port for the daemon to listen on Default: 9090. |
| `--host` | <host:string> | Host for the daemon to bind to Default: 127.0.0.1. |
| `--address` | <url:string> | The address clients reach this serve at, as they put it in serverAddress. Required to write a v3 datastore 'swamp datastore claim' gave to that address |
| `--advertise-address` | <url:string> | This node's own http(s) address, as the other serve nodes sharing its v3 datastore reach it. Followers forward writes to the leader at this address; without it a node bound to a wildcard or loopback host cannot be forwarded to |
| `--ca-cert` | <path:string> | PEM file of CA certificates to trust, besides the system store, when this node forwards to its team's leader (a relative path resolves against the repository) |
| `--no-schedule` |  | Disable scheduled workflow execution |
| `--cert-file` | <path:string> | Path to PEM-encoded TLS certificate (a relative path resolves against the repository) |
| `--key-file` | <path:string> | Path to PEM-encoded TLS private key (a relative path resolves against the repository) |
| `--grants-file` | <path:string> | Path to an external grants YAML file loaded at startup (a relative path resolves against the repository); its grants are stored with source file:grants-file |
| `--grants-dir` | <path:string> | Path to an additional directory of grants YAML files, read alongside the repository grants/ directory (a relative path resolves against the repository); their grants are stored with source file:grants-dir/<filename> |
| `--grant-reload` | <mode:string> | Policy snapshot reload mode: manual (default) or auto Default: manual. |
| `--webhook` | <spec:string> | Register a webhook endpoint: <route>:<workflow>:<secret>[:<scheme>[:<header>[:<prefix>]]]. scheme is one of github (default), jira, linear, stripe, slack, generic, or a webhook extension type (@collective/name). Secret may use @env=VAR to read from an environment variable, @file=/path to read from a file, or @vault=<vault>:<key> to read from a configured vault (avoids secrets in argv) |
| `--auth-mode` | <mode:string> | Authentication mode: none (default, deprecated), token, or oauth Default: none. |
| `--admins` | <principals:string> | Comma-separated principal IDs for admin access |
| `--allowed-collectives` | <list:string> | Comma-separated collective slugs for OAuth admission policy |
| `--allowed-users` | <list:string> | Comma-separated swamp-club usernames or user:<sub> subjects for OAuth admission policy |
| `--oauth-provider` | <url:string> | OAuth authorization server URL (default: https://swamp-club.com) |
| `--oauth-client-id` | <id:string> | OAuth client ID — auto-registered on first start if omitted. Set SWAMP_API_KEY, SWAMP_API_KEY_FILE or --club-api-key-file (a collective API token with oauth:manage scope) for headless registration without browser interaction. |
| `--club-api-key-file` | <path:string> | Path to a file containing the collective API key (oauth:manage scope) used for headless OAuth registration, username lookup, instance registration and heartbeat; overrides SWAMP_API_KEY_FILE and SWAMP_API_KEY |
| `--oauth-client-name` | <name:string> | OAuth client name used during registration (env: SWAMP_OAUTH_CLIENT_NAME). Defaults to swamp-serve-{repoName}-{hostname}. |
| `--groups-field` | <field:string> | Userinfo field name for group/collective memberships (default: collectives) |
| `--restricted-model-types` | <types:string> | Comma-separated behavior types whose behaviors only admins may create, run, edit or delete, along with their data and the workflow steps that run them (e.g. command/shell,@acme/deploy); a leading @ is ignored when matching, so @acme/deploy and acme/deploy are the same entry. Requires --auth-mode token or oauth |
| `--restricted-commands` | <cmds:string> | Comma-separated server commands that require admin authority (e.g. datastore.namespace.list,extension.install); names match exactly. Requires --auth-mode token or oauth |
| `--approve-requires-explicit-grant` |  | Require a grant that names approve to decide a manual approval gate; a run grant alone no longer implies approve. Off by default. Requires --auth-mode token or oauth (env: SWAMP_APPROVE_REQUIRES_EXPLICIT_GRANT) |
| `--signal-requires-explicit-grant` |  | Require a grant that names signal to deliver a signal to a workflow's wait; a run grant alone no longer implies signal. Off by default. Requires --auth-mode token or oauth (env: SWAMP_SIGNAL_REQUIRES_EXPLICIT_GRANT) |
| `--tag-requires-explicit-grant` |  | Require a grant that names tag to change a behavior's or workflow's tags; a write grant alone no longer implies tag. Off by default. Requires --auth-mode token or oauth (env: SWAMP_TAG_REQUIRES_EXPLICIT_GRANT) |
| `--group-refresh-interval` | <duration:string> | How often to re-fetch IdP group memberships for active server tokens. Accepts seconds (14400), explicit units (4h, 30m), or 0 to disable. Default: 4h. Requires --auth-mode oauth (env: SWAMP_GROUP_REFRESH_INTERVAL). |
| `--trust-proxy` |  | Trust X-Forwarded-For header for client IP in token auth rate limiting |
| `--verify-on-enroll` |  | Run a fleet probe on each enrolling worker before it becomes schedulable |
| `--trusted-hosts` | <hosts:string> | Comma-separated hostnames or host:port authorities to trust for Host and browser Origin validation, including no-auth HTTP APIs behind reverse proxies; give a public address on a port other than 443 as host:port (env: SWAMP_TRUSTED_HOSTS) |
| `--dispatch-env-allow` | <names:string> | Comma-separated environment variable names; only these ship to workers with each dispatch (case-insensitive, never HOME, PATH, SWAMP_* or the other denylisted names). Unset ships serve's whole environment minus the denylist. To ship none, set 'dispatch-env-allow: []' in serve.yaml or an empty SWAMP_DISPATCH_ENV_ALLOW (env: SWAMP_DISPATCH_ENV_ALLOW) |
| `--detach-runs` |  | Deprecated — HA mode is now detected automatically based on your datastore configuration. This flag is accepted for backwards compatibility but has no effect. |
| `--heartbeat-interval` | <duration:string> | Instance heartbeat interval (default: 30s, env: SWAMP_HEARTBEAT_INTERVAL) |
| `--stale-ttl` | <duration:string> | Heartbeat stale TTL — instance considered dead after this (default: 90s, env: SWAMP_STALE_TTL) |
| `--reconciliation-interval` | <duration:string> | Peer reconciliation scan interval (default: 60s, env: SWAMP_RECONCILIATION_INTERVAL) |
| `--hydration-timeout` | <duration:string> | Startup cache hydration timeout (default: 60s, env: SWAMP_HYDRATION_TIMEOUT) |
| `--shutdown-drain-timeout` | <duration:string> | How long shutdown waits for in-flight runs before aborting them (default: 30s, 0 aborts at once, env: SWAMP_SHUTDOWN_DRAIN_TIMEOUT) |
| `--datastore-poll-interval` | <duration:string> | Datastore poll interval (default: 30s, minimum: 1s, env: SWAMP_DATASTORE_POLL_INTERVAL) |
| `--continuation-sweep-interval` | <duration:string> | Continuation sweep interval (default: 30s, 0 disables, env: SWAMP_CONTINUATION_SWEEP_INTERVAL) |
| `--max-signal-wait-timeout` | <duration:string> | Longest timeout a wait_for_signal step may ask for (default: 1y, env: SWAMP_MAX_SIGNAL_WAIT_TIMEOUT) |
| `--token-gc-interval` | <duration:string> | Server token GC interval (default: 1h, 0 disables, env: SWAMP_TOKEN_GC_INTERVAL) |
| `--token-gc-grace-period` | <duration:string> | How long expired server tokens are kept before GC (default: 1h, 0 deletes at expiry, env: SWAMP_TOKEN_GC_GRACE_PERIOD) |
| `--remote-only` |  | Disable local (loopback) execution — all steps must declare placement (env: SWAMP_REMOTE_ONLY) |
| `--ws-idle-timeout` | <duration:string> | WebSocket idle timeout (env: SWAMP_WS_IDLE_TIMEOUT). Default: 30s |
| `--queue-timeout` | <duration:string> | Queue timeout for placed steps (env: SWAMP_QUEUE_TIMEOUT). Default: 10m |
| `--max-concurrent-runs` | <count:integer> | Maximum concurrent detached runs across all principals. Default: 100 (env: SWAMP_MAX_CONCURRENT_RUNS) |
| `--max-concurrent-scheduled-runs` | <count:integer> | Maximum scheduled workflow runs in flight at once; a workflow never overlaps itself. Default: 1 (env: SWAMP_MAX_CONCURRENT_SCHEDULED_RUNS) |
| `--max-concurrent-webhook-runs` | <count:integer> | Maximum webhook workflow runs in flight at once, across all routes; deliveries to the same route may overlap. Default: 1 (env: SWAMP_MAX_CONCURRENT_WEBHOOK_RUNS) |
| `--max-runs-per-principal` | <count:integer> | Maximum concurrent detached runs per authenticated principal (env: SWAMP_MAX_RUNS_PER_PRINCIPAL) |
| `--max-run-duration` | <duration:string> | Maximum wall-clock time a detached run may execute (env: SWAMP_MAX_RUN_DURATION) |
| `--hot-reload` |  | Enable SIGHUP-based hot-reload for pulled extension bundles. Writes a PID file to .swamp/serve.pid; use 'swamp serve reload' to trigger |
| `--enable-internal-api` |  | Enable the /internal/runs endpoint for full run history access (env: SWAMP_ENABLE_INTERNAL_API) |
| `--dashboard` |  | Enable the web dashboard at /dashboard (env: SWAMP_DASHBOARD) |
| `--auto-resume` |  | Resume a suspended run once every approval gate on it is decided and every wait for a signal is settled. Applies to workflows that declare no inputs; a workflow with inputs must set autoResume: true itself, and autoResume: false opts out (env: SWAMP_AUTO_RESUME) |

Common flags (see index.md): `--repo-dir`

## swamp serve daemon disable

Disable and remove the swamp serve daemon

| Flag | Value | Description |
|---|---|---|
| `--user` |  | Target the per-user service (systemd --user / launchd agent) |

## swamp serve daemon status

Show the status of the swamp serve daemon

| Flag | Value | Description |
|---|---|---|
| `--user` |  | Target the per-user service (systemd --user / launchd agent) |
