# swamp CLI: worker
Generated from `swamp help --json`, swamp 20261030.195233.0-sha.713d92e4. Do not edit by hand; regenerate with `python3 scripts/render_cli_reference.py`.

Root commands in this group: worker.

## swamp worker

Manage remote execution workers and enrollment tokens

## swamp worker token

Manage worker enrollment tokens

## swamp worker token create

Mint a named worker enrollment token; the plaintext is shown once

Arguments: name  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--duration` | <duration:string> | Token lifetime (e.g. 30m, 1h, 24h, 7d) — a hard deadline: the enrolled worker is disconnected when it elapses |
| `--vault` | <vault:string> | Vault on the server that stores the token plaintext (only with --server; defaults to _token-secrets, which local creation always uses) |
| `--max-enrollments` | <n:string> | Maximum machines this token can enroll (positive integer or "unlimited"). Default: 1 |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp worker token list

List worker enrollment tokens: state, expiry, and bound instance

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp worker token revoke

```text
Invalidate a worker enrollment token before it expires

Workers already connected on the token are disconnected and their
credentials revoked. With --server this happens at once; otherwise a
running orchestrator does it at its next token check, about every 30
seconds.
```

Arguments: name  (`?` marks optional)

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp worker list

List workers in the pool: status, labels, platform, and last seen

| Flag | Value | Description |
|---|---|---|
| `--all` |  | Include disconnected workers |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp worker queue

List steps currently queued for dispatch, waiting for a matching worker

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp worker connect

Connect this machine to an orchestrator as a remote execution worker

Arguments: url?  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--token` | <token:string> | Enrollment token (<name>.<secret>) (env: SWAMP_WORKER_TOKEN) |
| `--token-file` | <path:string> | Path to a file containing the enrollment token; mutually exclusive with --token (env: SWAMP_WORKER_TOKEN_FILE) |
| `--server-token` | <token:string> | Server access token for authenticating the WebSocket connection (<name>.<secret>) (env: SWAMP_SERVER_TOKEN) |
| `--server-token-file` | <path:string> | Path to a file containing the server access token; mutually exclusive with --server-token (env: SWAMP_SERVER_TOKEN_FILE) |
| `--label` | <label:string> | Scheduling label key=value (repeatable) (env: SWAMP_WORKER_LABELS, comma-separated) |
| `--data-plane-url` | <url:string> | Override the data-plane base URL (defaults to the connect URL over HTTP) |
| `--cache-dir` | <dir:string> | Bundle/asset cache directory; also stores the machine id the enrollment token binds to — set a stable directory so the worker can re-enroll after a restart (defaults to a fresh temp dir) (env: SWAMP_WORKER_CACHE_DIR) |
| `--no-reconnect` |  | Exit when the control socket closes |
| `--max-dispatches` | <n:number> | Drain and exit 0 after N dispatches complete (env: SWAMP_WORKER_MAX_DISPATCHES) |
| `--idle-timeout` | <duration:string> | Drain and exit 0 after being continuously idle for this duration (e.g. 30s, 5m, 1h) (env: SWAMP_WORKER_IDLE_TIMEOUT) |
| `--concurrency` | <n:string> | Number of concurrent dispatch slots ("auto" = CPU count, min 1). Default: 1 (env: SWAMP_WORKER_CONCURRENCY) |
| `--ca-cert` | <path:string> | Path to PEM-encoded CA certificate to trust for TLS connections to the orchestrator (env: SWAMP_CA_CERT) |

## swamp worker verify

Run a fleet probe on connected workers to verify enrollment, scheduling, capability RPC, and data plane connectivity

Arguments: name?  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--label` | <label:string> | Filter workers by label key=value (repeatable) |

Common flags (see index.md): `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp worker daemon

Manage swamp worker as a system daemon (EXPERIMENTAL)

## swamp worker daemon enable

Enable swamp worker as a system daemon (launchd/systemd). SWAMP_SERVE_EXTRA_HEADERS set in this shell is written into the service, as worker connect would read it; sudo drops it unless run as sudo -E or sudo --preserve-env=SWAMP_SERVE_EXTRA_HEADERS.

Arguments: url?  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--user` |  | Install as a per-user service (systemd --user / launchd agent) |
| `--token` | <token:string> | Enrollment token (<name>.<secret>) |
| `--token-file` | <path:string> | Path to a file containing the enrollment token; mutually exclusive with --token |
| `--server-token` | <token:string> | Server access token for authenticating the WebSocket connection (<name>.<secret>) |
| `--server-token-file` | <path:string> | Path to a file containing the server access token; mutually exclusive with --server-token |
| `--label` | <label:string> | Scheduling label key=value (repeatable) |
| `--cache-dir` | <dir:string> | Bundle/asset cache directory; also stores the machine id |
| `--data-plane-url` | <url:string> | Override the data-plane base URL |
| `--max-dispatches` | <n:number> | Drain and exit 0 after N dispatches complete |
| `--idle-timeout` | <duration:string> | Drain and exit 0 after being continuously idle for this duration (e.g. 30s, 5m, 1h) |
| `--no-reconnect` |  | Exit when the control socket closes |
| `--concurrency` | <n:string> | Number of concurrent dispatch slots ("auto" = CPU count of the machine running the service, min 1). Default: 1 |
| `--ca-cert` | <path:string> | Path to PEM-encoded CA certificate to trust for TLS connections to the orchestrator; a system service must be able to read it |

## swamp worker daemon disable

Disable and remove the swamp worker daemon

| Flag | Value | Description |
|---|---|---|
| `--user` |  | Target the per-user service (systemd --user / launchd agent) |

## swamp worker daemon status

Show the status of the swamp worker daemon

| Flag | Value | Description |
|---|---|---|
| `--user` |  | Target the per-user service (systemd --user / launchd agent) |

## swamp worker prune

Remove stale disconnected worker records (binding cleanup runs server-side)

| Flag | Value | Description |
|---|---|---|
| `--grace-period` | <duration:string> | Only prune workers disconnected longer than this (default: 24h) |
| `--dry-run` |  | Preview what would be pruned without deleting |

Common flags (see index.md): `--repo-dir`, `-y, --yes`, `-f, --force`, `--server`, `--token`, `--token-file`, `--ca-cert`
