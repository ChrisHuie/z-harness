# swamp CLI: vault
Generated from `swamp help --json`, swamp 20261030.195233.0-sha.713d92e4. Do not edit by hand; regenerate with `python3 scripts/render_cli_reference.py`.

Root commands in this group: vault.

## swamp vault

Manage vault configurations

## swamp vault type

Inspect vault types

## swamp vault type search (alias: list)

Search for vault types

Arguments: query?  (`?` marks optional)

Common flags (see index.md): `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp vault create

```text
Create a new vault configuration

With --server, a local_encryption vault cannot set its key-source fields
(base_dir, key_file, ssh_key_path, auto_generate) to anything other
than the server's defaults. Leave them out and the server's defaults are used.
```

Arguments: type, name?  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--config` | <json:string> | Provider configuration as JSON |
| `--audit-reads` |  | Enable read access audit trail for this vault (can also be set later with vault edit) |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp vault search (alias: list)

Search for vaults in the repository

Arguments: query?  (`?` marks optional)

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp vault get

Show details of a vault configuration

Arguments: vault_name_or_id, extra?  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `-t, --type` | <type:string> | Vault type (optional, narrows search) |
| `--pull` |  | Pull config from the remote datastore before reading (for managedConfig deployments) |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp vault describe

Describe a vault configuration

Arguments: vault_name_or_id  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `-t, --type` | <type:string> | Vault type (optional, narrows search) |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp vault edit

```text
Edit a vault configuration file

With --server, a local_encryption vault's key-source fields
(base_dir, key_file, ssh_key_path, auto_generate) must keep their
stored values. Repairing a vault whose YAML no longer parses refuses any
value for them other than the server's defaults, and stores those defaults.
```

Arguments: vault_name_or_id?  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `-t, --type` | <type:string> | Vault type (optional, narrows search) |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp vault put (alias: write-secret)

```text
Store a secret in a vault.

The value can be provided in several ways:
  - As a third argument:   swamp vault put <vault> <key> <value>
  - Inline with KEY=VALUE: swamp vault put <vault> KEY=VALUE
  - Piped via stdin:       echo "val" | swamp vault put <vault> <key>
  - Interactive prompt:    swamp vault put <vault> <key>  (prompts with hidden input)

Piping via stdin is recommended for scripts and CI to avoid exposing secrets in the process argument list.

When using --server, the value must be passed as a positional argument or KEY=VALUE form — stdin and interactive prompts are not available remotely.
```

Arguments: vault_name, key, value?  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `-y, --yes` |  | Skip confirmation prompt when overwriting |
| `-f, --force` |  | Skip confirmation prompt when overwriting (alias for --yes) |
| `--refresh-from` | <command:string> | Command to run to refresh the secret value when the TTL expires |
| `--refresh-ttl` | <duration:string> | How long before the secret is considered stale (e.g. 50m, 1h, 30s) |
| `--clear-refresh` |  | Remove the refresh hook from this secret |
| `--label` | <label:string> | Attach a metadata label to the secret (key=value, repeatable) |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp vault delete

```text
Delete a secret from a vault.

Removes the secret and any associated metadata (annotations, refresh hooks).
Use --force to skip the confirmation prompt and to treat non-existent keys as a no-op.

When using --server, the confirmation prompt is not available — use --force to suppress the error on missing keys.
```

Arguments: vault_name, key  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `-f, --force` |  | Skip confirmation prompt (alias for --yes) and succeed when the key is missing |

Common flags (see index.md): `--repo-dir`, `-y, --yes`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp vault remove

```text
Remove a vault.

Removes the vault's config. For a local_encryption vault it then permanently
deletes the vault's stored secrets, annotations, refresh hooks and generated
key; this cannot be undone. For other vault types only the local config is
removed, and the secrets stay with their provider.

The repository's default vault (defaultVault in .swamp.yaml, or the first vault
when none is set) is never removed. Secrets stored outside this repository are
kept.
A vault that behaviors, workflows or the datastore config reference is refused
unless --force is given. Unlike 'vault delete', --force here does not skip the
confirmation; use --yes for that.

In log mode the command asks for confirmation unless --yes is given. With
--json it does not prompt.

To delete a single secret, use 'swamp vault delete <vault> <key>'.
```

Arguments: vault_name  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `-f, --force` |  | Remove the vault even while behaviors, workflows or the datastore config reference it (not an alias for --yes) |

Common flags (see index.md): `--repo-dir`, `-y, --yes`

## swamp vault annotate

```text
Annotate a vault secret with metadata.

Attaches provenance metadata (URL, notes, labels) to an existing secret.
Annotations use merge semantics: only the fields you specify are updated,
existing fields are preserved. Use --clear to remove all annotations.
```

Arguments: vault_name, key  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--url` | <url:string> | URL associated with this secret |
| `--notes` | <notes:string> | Free-text notes about this secret |
| `--label` | <label:string> | Key=value label (repeatable) |
| `--clear` |  | Remove all annotations from this secret |
| `--remove-label` | <key:string> | Remove a label by key (repeatable) |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp vault inspect

```text
Show metadata for a vault secret.

Displays size, type, annotations, and refresh-hook info for a secret
without exposing the secret value. Works on all vault providers; annotation
and refresh-hook fields are omitted when not supported.
```

Arguments: vault_name, key  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--pull` |  | Pull config from the remote datastore before reading (for managedConfig deployments) |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp vault migrate

```text
Migrate a vault to a different backend type.

Copies all secrets from the current backend to a new one, then updates
the vault configuration. The vault name stays the same, so all existing
vault references continue to work without modification.

Both the source and target vaults must be different types.

With --server, a local_encryption target cannot set its key-source fields
(base_dir, key_file, ssh_key_path, auto_generate) to anything other
than the server's defaults. Leave them out and the server's defaults are used.
```

Arguments: vault_name  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--to-type` | <type:string> | Target vault type |
| `--config` | <config:string> | Provider-specific config as JSON (e.g. '{"region":"us-east-1"}') |
| `--dry-run` |  | Preview migration without making changes |

Common flags (see index.md): `-y, --yes`, `-f, --force`, `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp vault read-secret

```text
Read a secret value from a vault.

In interactive (log) mode, prompts for confirmation before revealing the secret
unless --force is set. In --json mode, outputs the value directly.
```

Arguments: vault_name, key  (`?` marks optional)

Common flags (see index.md): `--repo-dir`, `-y, --yes`, `-f, --force`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp vault list-keys

```text
List all secret keys in a vault (without values)

The vault name is required. Omitting it fails with the available vaults.
```

Arguments: vault_name?  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--pull` |  | Pull config from the remote datastore before reading (for managedConfig deployments) |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp vault audit-trail

View the vault audit trail.

| Flag | Value | Description |
|---|---|---|
| `--vault` | <name:string> | Filter by vault name |
| `--key` | <key:string> | Filter by secret key |
| `--action` | <action:string> | Filter by action: get, put, delete, annotate |
| `--since` | <date:string> | Start date, e.g. 2026-07-01 or 2026-07-01T00:00:00Z [default: 7 days ago] |
| `--until` | <date:string> | End date, e.g. 2026-07-01 or 2026-07-01T00:00:00Z [default: now] |
| `--limit` | <count:integer> | Maximum number of entries to return [default: 100] |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`
