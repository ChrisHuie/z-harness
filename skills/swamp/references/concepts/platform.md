# Datastore, serve, access control, workers

## Datastore

The default is the filesystem under `.swamp/`. `swamp datastore setup extension <type>
--config '<json>' [--namespace <slug>] [--hydration-strategy full|lazy] [--format 2|3]`
moves runtime data to `@swamp/s3-datastore` or `@swamp/gcs-datastore`; pull the extension
first. Format 2 is files; format 3 is a commit log with one writer at a time
(`datastore_v3_writer_busy` exits 75) and `config_edit_conflict` when two checkouts edit the
same definition. Namespaces give provenance inside a shared bucket, not isolation; secrets are
never shared through a datastore. `swamp datastore status`, `sync [--pull|--push]`, `lock
status|release --force`, `namespace set|unset|migrate|list`, `config migrate` (managed
config), `claim` and `release` (serve as the sole writer of a v3 store), `compact`, `gc`.
`swamp doctor datastores [--retention] [--repair -y]` is the health and repair entry point.

## Serve

`swamp serve` starts the WebSocket API on loopback. Off loopback it needs TLS (`--cert-file`,
`--key-file`) and `--auth-mode token|oauth`. Clients reach it with `--server <url>` on most
commands or `SWAMP_SERVE_URL`, and authenticate with `swamp auth server-login` (OAuth device
flow or `--token`). `swamp repo init --server <url>` records a default `serverAddress`.

Flag themes: auth and admission (`--admins`, `--allowed-users`, `--allowed-collectives`,
`--oauth-provider`, `--club-api-key-file`, `--trusted-hosts`, `--trust-proxy`); policy
(`--grants-file`, `--grants-dir`, `--grant-reload`, `--restricted-model-types`,
`--restricted-commands`, the three `--*-requires-explicit-grant` switches); triggers
(`--no-schedule`, `--webhook '<route>:<workflow>:<secret>[:<scheme>[:<header>[:<prefix>]]]'`
with `@env=`, `@file=`, `@vault=<vault>:<key>` secrets and schemes github, jira, linear, stripe,
slack, generic or an extension type); runs (`--auto-resume`, `--max-concurrent-runs`,
`--max-run-duration`); workers (`--queue-timeout`, default 10m, `--verify-on-enroll`,
`--remote-only`, `--dispatch-env-allow`); surfaces (`--dashboard`, `--enable-internal-api`,
`--hot-reload` with `swamp serve reload`). `swamp serve check-config` validates auth settings,
grant files and the token-secrets key without starting. `swamp serve daemon enable|disable|status`
is experimental. A service unit must set `SWAMP_HOME` or scheduled runs fail with an unknown
behavior type. REST: `/health`, `/ready`, `/api/v1/health`, cancel endpoints, `/internal/runs`.

## Access control

Actions: `run`, `read`, `write`, `approve`, `signal`, `tag`, `admin`. Resources:
`workflow:<name or @ns/*>`, `behavior:<...>`, `data:*`, `vault:<name>`, `access:*`. Default
deny; an explicit deny wins. By default `run` implies `approve` and `signal`, and `write`
implies `tag`; the explicit-grant switches on serve turn that off for separation of duties.

```bash
swamp access grant create --subject user:x --allow run,read --on 'workflow:@acme/*' [--when '<CEL>'] [--methods read,list]
swamp access grant list [--subject] [--on] ; swamp access grant revoke <grant-id>
swamp access group create <g> ; add-member <g> <principal> ; members <g> ; list-idp --server <url>
swamp access can-i --server <url> --action run --on workflow:deploy
swamp access check --subject user:x --action approve --on workflow:deploy
swamp access token mint <name> --principal user:<id> --duration 30d ; reveal ; rotate ; revoke ; list
swamp access reload
```

Grants may also live as YAML under `grants/`. Token secrets live in the `_token-secrets` vault.

## Workers

```bash
swamp worker token create <name> --duration 1h [--max-enrollments N|unlimited]   # plaintext shown once
swamp serve --port 9090
swamp worker connect ws://host:9090 --token <name.secret> --cache-dir <stable dir> --label os=linux [--concurrency auto]
swamp worker list ; swamp worker queue ; swamp worker verify [--label k=v] ; swamp worker prune [--dry-run]
swamp workflow run <wf> --server ws://host:9090 [--detach]
```

Placement (`target` or `labels`, plus `platform`, `queueTimeout`, `affinity`) inherits workflow
to job to step; `labels: {}` on a step clears inherited labels; `target` and `labels` are
mutually exclusive. A placed step queues up to the queue timeout for a matching worker. Only
environment variables named in `--dispatch-env-allow` ship to workers; `HOME`, `PATH` and
`SWAMP_*` never do. Use a stable `--cache-dir` so a worker can re-enroll after a restart.
`runModel` from extension code is unavailable on workers.
