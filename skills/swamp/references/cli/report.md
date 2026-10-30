# swamp CLI: report
Generated from `swamp help --json`, swamp 20261030.195233.0-sha.713d92e4. Do not edit by hand; regenerate with `python3 scripts/render_cli_reference.py`.

Root commands in this group: report.

## swamp report

Browse and view stored report results

## swamp report type

Inspect report types

## swamp report type search (alias: list)

Search for report types

Arguments: query?  (`?` marks optional)

Common flags (see index.md): `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp report search

Search stored report results across all behaviors and workflows

Arguments: query?  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--behavior, --model` | <name:string> | Filter to a specific behavior (--model is the kept legacy spelling) |
| `--workflow` | <name:string> | Filter to a specific workflow |
| `--scope` | <scope:string> | Filter by report scope (method, behavior or model, workflow) |
| `--type` | <name:string> | Filter by exact report type name (e.g. @webframp/cost-audit-report) |
| `--label` | <label:string> | Filter by report label (repeatable) |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp report get

Show a stored report's content

Arguments: report_name  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--behavior, --model` | <name:string> | Scope to a specific behavior (--model is the kept legacy spelling) |
| `--workflow` | <name:string> | Scope to a specific workflow |
| `--variant` | <variant:string> | Select a specific forEach variant |
| `--markdown` |  | Output as plain markdown instead of terminal-formatted |
| `--max-width` | <width:number> | Cap total output width in columns (env: SWAMP_REPORT_MAX_WIDTH) |
| `--max-col-width` | <width:number> | Cap individual table column width in characters (env: SWAMP_REPORT_MAX_COL_WIDTH) |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp report describe

Show report definition metadata from the registry

Arguments: report_name  (`?` marks optional)

Common flags (see index.md): `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp report list

List registered report definitions

Arguments: query?  (`?` marks optional)

Common flags (see index.md): `--server`, `--token`, `--token-file`, `--ca-cert`
