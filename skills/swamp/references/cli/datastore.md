# swamp CLI: datastore
Generated from `swamp help --json`, swamp 20261030.195233.0-sha.713d92e4. Do not edit by hand; regenerate with `python3 scripts/render_cli_reference.py`.

Root commands in this group: datastore.

## swamp datastore

Manage datastore configuration

## swamp datastore type

Inspect datastore types

## swamp datastore type search (alias: list)

Search for datastore types

Arguments: query?  (`?` marks optional)

## swamp datastore status

Show datastore configuration and health

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp datastore setup

Configure a datastore for this repository

Common flags (see index.md): `--repo-dir`

## swamp datastore setup filesystem

Set up a filesystem datastore

| Flag | Value | Description |
|---|---|---|
| `--path` | <path:string> | Path for the datastore directory |
| `--directories` | <dirs:string[]> | Subdirectories to store in the datastore (comma-separated) |
| `--skip-migration` |  | Skip copying existing data into the target path |
| `--format` | <format:integer> | Datastore format: 2 (files, default) or 3 (v3 commit log; needs a new, empty path and a repository with no data; one writer at a time) |

Common flags (see index.md): `--repo-dir`

## swamp datastore setup extension

Set up an extension-provided datastore (e.g., @swamp/s3-datastore)

Arguments: type  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--config` | <config:string> | JSON config object for the extension (e.g., '{"bucket":"name","region":"us-east-1"}') |
| `--namespace` | <slug:string> | Namespace to scope this datastore to (avoids absorbing foreign data from shared prefixes) |
| `--skip-migration` |  | Skip pushing local .swamp/ data to the remote (does not skip remote→local cache hydration, which always runs) |
| `--hydration-strategy` | <strategy:string> | Content download strategy: "full" (default, download everything) or "lazy" (metadata only, download content on demand) |
| `--timeout` | <seconds:integer> | Override the sync timeout for the initial push and hydration pull (seconds, max 21600). Wins over SWAMP_DATASTORE_SYNC_TIMEOUT_MS. Preferred escape hatch for large first-time setups. |
| `--format` | <format:integer> | Datastore format: 2 (the default) or 3, the v3 commit log, replicated to the bucket through Litestream. Format 3 needs @swamp/s3-datastore or @swamp/gcs-datastore 2026.10.16.5 or later, installed and pinned in the lockfile (run `swamp extension pull <type>` first, or `swamp extension update <type>` if it is installed), a new, empty bucket prefix and a repository with no records |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp datastore setup s3

(Removed) Use: swamp datastore setup extension @swamp/s3-datastore --config '{...}'

Arguments: args?  (`?` marks optional)

## swamp datastore sync

Sync local cache with S3 datastore

| Flag | Value | Description |
|---|---|---|
| `--pull` |  | Pull-only mode (fetch all remote data to local cache) |
| `--push` |  | Push-only mode (upload all local cache data to S3) |
| `-y, --yes` |  | Skip the push preview and upload immediately |
| `--confirm` |  | Skip the push preview and upload immediately (alias for --yes) |
| `--timeout` | <seconds:integer> | Override the per-direction sync timeout for this invocation (seconds, max 21600). Wins over SWAMP_DATASTORE_SYNC_TIMEOUT_MS and per-datastore config. Preferred escape hatch for one-off large syncs. |

Common flags (see index.md): `--repo-dir`

## swamp datastore lock

Manage datastore locks

## swamp datastore lock status

Show who holds the datastore lock

Common flags (see index.md): `--repo-dir`

## swamp datastore lock release

Force-release a stuck datastore lock

| Flag | Value | Description |
|---|---|---|
| `--force` |  | Required to confirm force release (not an alias for --yes) |
| `--behavior, --model` | <behavior:string> | Release a specific behavior's lock (type/id format, e.g. aws-ec2/my-server; --model is the kept legacy spelling) |

Common flags (see index.md): `--repo-dir`

## swamp datastore compact

Checkpoint the WAL and vacuum the catalog database to reclaim disk space

Common flags (see index.md): `--repo-dir`

## swamp datastore gc

Delete content chunks no commit names any more (v3 datastores)

Common flags (see index.md): `--repo-dir`

## swamp datastore claim

Make swamp serve the owner of a v3 datastore: direct writes are refused, and writes go through serve

| Flag | Value | Description |
|---|---|---|
| `--address` | <url:string> | The address clients reach serve at, as they put it in serverAddress |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp datastore release

Remove swamp serve's claim on a v3 datastore, so checkouts write it directly again

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp datastore migrate-index

Migrate the datastore index from monolithic to shard-first format

Common flags (see index.md): `--repo-dir`

## swamp datastore catalog

Manage datastore catalog

## swamp datastore catalog pull

Pull catalog metadata from foreign namespaces

| Flag | Value | Description |
|---|---|---|
| `--namespaces` | <namespaces:string> | Comma-separated list of foreign namespaces to pull |

Common flags (see index.md): `--repo-dir`

## swamp datastore namespace

Manage datastore namespace

## swamp datastore namespace set

Assign a namespace to this repository

Arguments: slug  (`?` marks optional)

Common flags (see index.md): `--repo-dir`

## swamp datastore namespace unset

Remove namespace from this repository

| Flag | Value | Description |
|---|---|---|
| `--migrate` |  | Also reverse-migrate data back to un-namespaced layout |
| `-y, --yes` |  | Execute the migration (required with --migrate, ignored otherwise) |
| `--confirm` |  | Execute the migration (alias for --yes) |

Common flags (see index.md): `--repo-dir`

## swamp datastore namespace migrate

Migrate data to namespaced layout (use --reverse to undo)

| Flag | Value | Description |
|---|---|---|
| `-y, --yes` |  | Execute the migration (without this flag, only a preview is shown) |
| `--confirm` |  | Execute the migration (alias for --yes) |
| `--reverse` |  | Reverse-migrate from namespaced layout back to solo layout |

Common flags (see index.md): `--repo-dir`

## swamp datastore namespace list

List all namespaces in the datastore

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp datastore config

Manage datastore-managed configuration

## swamp datastore config migrate

```text
Migrate configuration into the datastore.

Copies behavior definitions, workflow definitions, vault configs,
the extension lockfile, and pulled extensions into the datastore
config tier. Sets managedConfig: true in .swamp.yaml if not already
set, including when another repo has already migrated the datastore.
Idempotent — safe to re-run: the datastore's migration sentinel
prevents duplicate work, and a re-run after a failed push publishes
the migration.

On a v3 datastore it commits the behavior definitions, workflow
definitions and vault configs not already in the datastore; a
re-run commits nothing. The extension lockfile is committed with
them, and pulled extensions are copied in this checkout only.
```

| Flag | Value | Description |
|---|---|---|
| `--repo-dir` | <dir:string> | Path to the swamp repository |
