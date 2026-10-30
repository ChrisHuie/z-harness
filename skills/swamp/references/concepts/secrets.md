# Vaults and secrets

## The default vault

`swamp repo init` creates a `local_encryption` vault named `default` and sets
`defaultVault: default` in `.swamp.yaml` unless run with `--no-vault`. Its key and secret
values live under `.swamp/secrets/` on the machine that wrote them; a clone starts with the
vault empty. Vault definition files under `vaults/<type>/<id>.yaml` carry no values and are
safe to commit. `swamp vault remove` refuses the vault that `defaultVault` names.

Create another vault only for a different provider or to keep secrets apart:
`swamp vault type search`, then `swamp vault create <type> <name> --config '<json>' --json`,
then edit the scaffold if needed. Never generate a vault id or write the YAML from scratch.

## Storing and reading

| Task | Command |
|---|---|
| Store (recommended for scripts) | `echo "$VALUE" \| swamp vault put <vault> <KEY>` |
| Store interactively | `swamp vault put <vault> <KEY>` (hidden prompt) |
| Store inline (visible in the process list) | `swamp vault put <vault> KEY=VALUE` |
| Auto-refresh | `swamp vault put <vault> <KEY> --refresh-from '<cmd>' --refresh-ttl 50m` |
| Read a value | `swamp vault read-secret <vault> <KEY> --force --json` |
| Keys only | `swamp vault list-keys <vault>` |
| Metadata without the value | `swamp vault inspect <vault> <KEY>` |
| Provenance | `swamp vault annotate <vault> <KEY> --url ... --notes ... --label k=v` |
| Access log | `swamp vault audit-trail [--vault] [--key] [--action get\|put\|delete\|annotate] [--since]` |
| Move backends | `swamp vault migrate <vault> --to-type <type> [--config] [--dry-run]` |

With `--server`, `put` takes the value as a positional or `KEY=VALUE`; stdin and prompts are
unavailable remotely.

## Referencing

`${{ vault.get('default', 'API_KEY') }}` in a definition or step resolves at run time; the file
stores the reference, not the value. `vault.put(vault, key, value)` stores a value a method
produced. Sensitive fields in a type's output schema are vaulted automatically; see the
resolution order in references/concepts/data-retention.md.

## Allow lists and grants

A workflow's top-level `vaults:` list caps which vaults any step may read and where sensitive
outputs may land; `swamp workflow validate` reports a step whose outputs would land elsewhere.
Over `swamp serve`, grants on `vault:<name>` govern access, and a principal's vault allow also
limits which vaults its runs can resolve.

## Diagnostics

`swamp doctor secrets` finds cleartext sensitive global arguments and says how to migrate each.
`swamp doctor vaults` finds sensitive outputs with no vault configured. Extension vault types
read their own credentials from the environment, an IAM role or a CLI login, never from the
vault `config`, which is stored as plain text.
