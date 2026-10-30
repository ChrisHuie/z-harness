# swamp CLI: operations
Generated from `swamp help --json`, swamp 20261030.195233.0-sha.713d92e4. Do not edit by hand; regenerate with `python3 scripts/render_cli_reference.py`.

Root commands in this group: audit, doctor, run, summarise.

## swamp summarise (alias: summarize)

Show a high-level overview of repo activity (method executions, workflows, data)

| Flag | Value | Description |
|---|---|---|
| `--since` | <duration:string> | Time window (e.g. 1h, 1d, 7d, 1w) Default: 7d. |
| `--limit` | <n:number> | Cap per-group run details (counts still reflect all matching runs) |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp doctor

Run diagnostics that verify swamp's integrations are healthy.

Common flags (see index.md): `--repo-dir`

## swamp doctor audit

Verify that the AI-tool audit integration is healthy for the configured tool.

| Flag | Value | Description |
|---|---|---|
| `--tool` | <tool:string> | Override the tool from .swamp.yaml (amp \| claude \| cursor \| kiro \| opencode \| codex \| copilot \| pi \| antigravity \| none) |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp doctor datastores

Check that the configured datastore is healthy and flag any vault compatibility issues.

| Flag | Value | Description |
|---|---|---|
| `--repair` |  | Preview and repair datastore issues: unreadable data versions, catalog index completeness, root-level unmigrated data, and foreign namespace contamination (add -y to execute). |
| `-y, --yes` |  | Execute the repair (without this, --repair shows a preview). |
| `--retention` |  | Also scan storage for workflow runs, snapshots, outputs, data versions and audit logs older than the garbageCollection retention in .swamp.yaml, and show each kind's last retention pass. |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp doctor extensions

Verify that user-defined extensions in this repo load cleanly and inspect catalog aggregate state.

| Flag | Value | Description |
|---|---|---|
| `--verbose` |  | Show per-source detail for each extension |
| `--repair` |  | Prune Tombstoned catalog rows and evict unreferenced bundle files |
| `--dry-run` |  | Preview repair operations without executing (use with --repair) |
| `-y, --yes` |  | Skip confirmation prompt (use with --repair) |
| `-f, --force` |  | Skip confirmation prompt (alias for --yes; use with --repair) |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp doctor install

Check swamp installation health: binary ownership, writability, autoupdate status.

## swamp doctor secrets

Scan behavior definitions for cleartext sensitive global arguments and report how to migrate each to a vault.

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp doctor vaults

Scan behavior definitions for sensitive resource outputs and verify a vault is configured to store them.

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp doctor workflows

Check that workflow YAML files in this repo load cleanly.

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp run

Track and diagnose in-flight method and workflow runs

## swamp run history

List active and recent runs (methods and workflows)

| Flag | Value | Description |
|---|---|---|
| `--active` |  | Show only currently running (mutually exclusive with --all) |
| `--all` |  | Show all tracked runs, not just recent (mutually exclusive with --active) |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp run doctor

Diagnose stale or orphaned runs

| Flag | Value | Description |
|---|---|---|
| `--fix` |  | Automatically reap stale runs |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp run gc

Garbage-collect old workflow runs, their evaluated-workflow snapshots, and method outputs. Orphaned snapshots are removed once past retention. Running and suspended runs are never deleted regardless of age.

| Flag | Value | Description |
|---|---|---|
| `--dry-run` |  | Show what would be deleted without deleting |
| `--older-than` | <duration:string> | Retention period. Units: m=minutes, h=hours, d=days, w=weeks, mo=months, y=years (e.g. 7d, 2w, 1mo). Overrides .swamp.yaml garbageCollection; default: 30d |

Common flags (see index.md): `--repo-dir`, `-y, --yes`, `-f, --force`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp audit

Hidden: omitted from `swamp help`; shown by `swamp help audit`.

View audit timeline of swamp vs direct CLI commands

| Flag | Value | Description |
|---|---|---|
| `--hours` | <hours:number> | Number of hours to analyze Default: 24. |
| `--all` |  | Show all commands including noise (ls, cat, etc.) |
| `--session` | <id:string> | Filter by session ID |
| `--include-diagnostic` |  | Include rows written by `swamp doctor audit`'s smoke test (filtered by default) |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp audit record

Hidden: omitted from `swamp help`; shown by `swamp help audit record`.

Record a bash command from a hook

| Flag | Value | Description |
|---|---|---|
| `--from-hook` |  | Required: indicates input comes from a hook |
| `--tool` | <tool:string> | AI tool providing hook input Default: claude. |

Common flags (see index.md): `--repo-dir`

## swamp audit alerts

Hidden: omitted from `swamp help`; shown by `swamp help audit alerts`.

List active audit alert rules and their current state

Common flags (see index.md): `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp audit export

Hidden: omitted from `swamp help`; shown by `swamp help audit export`.

Bulk export audit events for compliance

| Flag | Value | Description |
|---|---|---|
| `--since` | <date:string> | Start time (ISO 8601) |
| `--until` | <date:string> | End time (ISO 8601) |
| `--format` | <fmt:string> | Output format: json, cef, csv [default: json] Default: json. |
| `--output` | <path:string> | Write output to file instead of stdout |
| `--principal` | <id:string> | Filter by principal ID |
| `--category` | <cat:string> | Filter by audit category (auth, access, execution, secrets, admin, data, system) |
| `--action` | <action:string> | Filter by action |
| `--outcome` | <outcome:string> | Filter by outcome (success, failure, denied) |
| `--resource` | <name:string> | Filter by resource name |

Common flags (see index.md): `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp audit log

Hidden: omitted from `swamp help`; shown by `swamp help audit log`.

Query the serve audit log

| Flag | Value | Description |
|---|---|---|
| `--since` | <date:string> | Start time, e.g. 2026-09-01T00:00:00Z [default: 24 hours ago] |
| `--until` | <date:string> | End time, e.g. 2026-09-02T00:00:00Z [default: now] |
| `--principal` | <id:string> | Filter by principal ID |
| `--category` | <cat:string> | Filter by audit category (auth, access, execution, secrets, admin, data, system) |
| `--action` | <action:string> | Filter by action |
| `--outcome` | <outcome:string> | Filter by outcome (success, failure, denied) |
| `--cursor` | <token:string> | Pagination cursor from a previous query |
| `--limit` | <count:integer> | Max events to return [default: 100] Default: 100. |
| `--follow` |  | Stream new audit events in real-time after the initial query (Ctrl+C to stop). In JSON mode, emits one event object per line (NDJSON). |

Common flags (see index.md): `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp audit report

Hidden: omitted from `swamp help`; shown by `swamp help audit report`.

Run an audit compliance report

Arguments: name?  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--list` |  | List available compliance reports |
| `--since` | <date:string> | Start date, e.g. 2026-09-01T00:00:00Z |
| `--until` | <date:string> | End date, e.g. 2026-09-10T00:00:00Z |

Common flags (see index.md): `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp audit rotate-key

Hidden: omitted from `swamp help`; shown by `swamp help audit rotate-key`.

Rotate the HMAC key used for audit event hashing

Common flags (see index.md): `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp audit verify

Hidden: omitted from `swamp help`; shown by `swamp help audit verify`.

Verify audit log chain integrity

| Flag | Value | Description |
|---|---|---|
| `--since` | <date:string> | Start time, e.g. 2026-09-01T00:00:00Z [default: 24 hours ago] |
| `--until` | <date:string> | End time, e.g. 2026-09-02T00:00:00Z [default: now] |

Common flags (see index.md): `--server`, `--token`, `--token-file`, `--ca-cert`
