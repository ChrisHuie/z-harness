# swamp CLI: data
Generated from `swamp help --json`, swamp 20261030.195233.0-sha.713d92e4. Do not edit by hand; regenerate with `python3 scripts/render_cli_reference.py`.

Root commands in this group: data.

## swamp data

Manage behavior data

## swamp data get

(Deprecated) Get data by behavior and name, or by workflow. Use 'swamp data query' instead; each read prints the equivalent query.

Arguments: behavior_id_or_name?, data_name?  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--behavior, --model` | <behavior:string> | Behavior name or ID (alternative to positional argument; --model is the kept legacy spelling) |
| `--name` | <name:string> | Data name (alternative to positional argument) |
| `--workflow` | <name:string> | Get data produced by a workflow |
| `--run` | <run_id:string> | Specific workflow run ID (defaults to latest) |
| `--no-content` |  | Show metadata only, without content |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp data list

List all data for a behavior or workflow, grouped by type

Arguments: behavior_id_or_name?  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--behavior, --model` | <behavior:string> | Behavior name or ID (alternative to positional argument; --model is the kept legacy spelling) |
| `--type` | <type:string> | Filter by data type tag (log, file, resource, data, output) |
| `--workflow` | <name:string> | List data produced by a workflow |
| `--run` | <run_id:string> | Specific workflow run ID (defaults to latest) |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp data search

Search for data across all behaviors

Arguments: query?  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--type` | <type:string> | Filter by data type tag (log, file, resource, data, output) |
| `--lifetime` | <lifetime:string> | Filter by lifetime (ephemeral, infinite, job, workflow, or duration) |
| `--lifecycle` | <lifecycle:string> | Filter by lifecycle (active, deleted) |
| `--owner-type` | <type:string> | Filter by owner type (behavior-method or model-method, workflow-step, manual) |
| `--workflow` | <name:string> | Filter to data tagged with this workflow name |
| `--behavior, --model` | <name:string> | Filter to data owned by this behavior name (--model is the kept legacy spelling) |
| `--content-type` | <mime:string> | Filter by MIME content type (e.g., application/json) |
| `--since` | <duration:string> | Only data created within duration (1h, 1d, 7d, 1w, 1mo) |
| `--output` | <output_id:string> | Data from a specific behavior output (by output ID) |
| `--run` | <run_id:string> | Data from a specific workflow run (by run ID) |
| `--tag` | <tag:string> | Filter by tag (KEY=VALUE, repeatable) |
| `--streaming` |  | Only show streaming data |
| `--limit` | <n:number> | Max results Default: 50. |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp data query

Query data artifacts using CEL predicates (interactive TUI when no predicate given)

Arguments: predicate?  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--limit` | <n:number> | Maximum results (unlimited when omitted) |
| `--select` | <expr:string> | CEL expression to extract fields from matching records (e.g. data.name) |
| `--single` |  | Require exactly one match; with --json, print the match (or its --select value) on its own instead of a results list |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp data versions

List all versions of specific data

Arguments: behavior_id_or_name?, data_name?  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--behavior, --model` | <behavior:string> | Behavior name or ID (alternative to positional argument; --model is the kept legacy spelling) |
| `--name` | <name:string> | Data name (alternative to positional argument) |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp data gc

Run garbage collection on data (lifecycle and versions)

| Flag | Value | Description |
|---|---|---|
| `--dry-run` |  | Show what would be deleted without deleting |

Common flags (see index.md): `--repo-dir`, `-y, --yes`, `-f, --force`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp data prune

```text
Reclaim orphaned data whose owning behavior definition no longer exists.
Unlike `data gc` (which enforces each behavior's declared lifetime and
version-cap), prune removes data left behind when a behavior definition is
deleted or migrated away. Deletion is irreversible; use --dry-run first.
```

| Flag | Value | Description |
|---|---|---|
| `--dry-run` |  | Show what would be reclaimed without deleting |

Common flags (see index.md): `--repo-dir`, `-y, --yes`, `-f, --force`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp data rename

Rename a data instance with backwards-compatible forwarding

Arguments: behavior_id_or_name?, old_name?, new_name?  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--behavior, --model` | <behavior:string> | Behavior name or ID (alternative to positional argument; --model is the kept legacy spelling) |
| `--name` | <name:string> | Current data name (alternative to positional argument) |
| `--new-name` | <newName:string> | New data name (alternative to positional argument) |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp data delete

Delete data artifacts: one by name, many by prefix, or all for a behavior

Arguments: behavior_id_or_name?, data_name?  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--behavior, --model` | <behavior:string> | Behavior name or ID (alternative to positional argument; --model is the kept legacy spelling) |
| `--name` | <name:string> | Data name (alternative to positional argument) |
| `--prefix` | <prefix:string> | Delete all data names starting with this prefix |
| `--all` |  | Delete all data for the behavior |
| `--dry-run` |  | Show what would be deleted without deleting |

Common flags (see index.md): `--repo-dir`, `-y, --yes`, `-f, --force`, `--server`, `--token`, `--token-file`, `--ca-cert`
