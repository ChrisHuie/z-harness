# Data, versions, lifetimes and retention

## Two kinds of output

| Kind | Content | Queryable |
|---|---|---|
| resource | JSON validated by the type's Zod schema | by attribute, through `swamp data query` and CEL `data.*` |
| file | opaque bytes with a MIME type | by metadata only; read with `file.contents()` |

Every write creates a new immutable version. Nothing is edited in place. The layout under the
datastore is `.swamp/data/<type>/<definition id>/<name>/<version>/` holding a metadata file and
the raw content, plus a `latest` pointer. Treat the layout as an implementation detail: read
through `swamp data query`, `swamp data list`, `swamp data versions`, never by grepping `.swamp/`.

## Lifetime, per output

| Value | Meaning |
|---|---|
| `ephemeral` | memory only, never written to disk; per-process budget `SWAMP_EPHEMERAL_BUDGET`, default 512mb |
| `job` | lives until the job completes |
| `workflow` | lives until the workflow run completes |
| duration | `1h`, `5m`, `10d`, `2w`, `1mo`, `10y`; `0h` normalizes to `workflow` |
| `infinite` | never deleted by lifetime |

Set in the type's output spec, overridden by the definition's `resources.<spec>.lifetime` or a
step's `dataOutputOverrides[].lifetime`. Step and definition overrides merge field by field; the
step wins on each field it sets.

## Garbage collection policy, per output

An integer keeps the N most recent versions; a duration keeps versions created within it.
`swamp data gc` applies the policy. With `autoGc: true` in `.swamp.yaml` it also applies at write
time and after each method run.

## Repository retention, in `.swamp.yaml`

```yaml
garbageCollection:
  retention: 30d        # fallback for workflowRuns, outputs, audit
  automatic: true       # serve: 5 minutes after start then hourly; CLI: at most once an hour
  workflowRuns: 14d
  evaluatedSnapshots: 3d
  outputs: 7d
  data: 30d             # opt-in only; ignores lifetime infinite and version caps
  audit: 90d
  bookkeeping: 24h      # serve worker records, enrollment tokens, leases, dispatches
```

Never removed automatically: unfinished runs and their snapshots, built-in access and serve
records, a data name with an unpromoted write, definitions, vaults, `.swamp.yaml`.

Manual passes: `swamp data gc` (lifetime and version caps), `swamp data prune` (data whose
definition no longer exists), `swamp run gc --older-than` (runs, snapshots, outputs),
`swamp datastore compact` and `swamp datastore gc` (space inside the store).

## Tags

Tags merge from the definition, the run (`--tag k=v`), the workflow, and step overrides. Query
with `tags.key == "value"` or `swamp data search --tag k=v`.

## Sensitive output

Fields marked sensitive in the type, or whole outputs marked sensitive, are stored as vault
references. Resolution order: field-level `vaultName`, then the spec or definition
`resources.<spec>.vaultName` or a step override, then `defaultVault`, then the first vault by
type and id. `swamp doctor vaults` reports a behavior that relies on the fallback.

## Rename and delete

`swamp data rename` leaves a forwarding marker so old references keep resolving.
`swamp data delete` takes one name, `--prefix`, or `--all` for a behavior; use `--dry-run`
first. Deletion is irreversible.
