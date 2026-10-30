# swamp CLI: index
Generated from `swamp help --json`, swamp 20261030.195233.0-sha.713d92e4. Do not edit by hand; regenerate with `python3 scripts/render_cli_reference.py`.

Totals: 297 commands (8 hidden), 1353 flag occurrences. The `swamp model` tree (28 commands) mirrors `swamp behavior` with the legacy spelling and is not expanded here.

## Root help

```text
AI Native Automation CLI

With --json, a command that fails writes its error to stderr as one JSON
document:

    { "error": "<message>", "code": "<error_code>" }

Match on "code" when it is present (an error without a stable identifier
has none, and other fields may appear); the message text can change
between releases.

Exit codes, shared by every command:

    0    success
    1    error
    2    unknown command or subcommand, or too many arguments
    75   temporary failure, such as lock contention or a temporary sign-in
         block; retry with backoff
    130  interrupted (Ctrl+C)

A command that adds codes of its own lists them in its help.
```

## Global flags

| Flag | Value | Description |
|---|---|---|
| `--json` |  | Output in JSON format (non-interactive) |
| `--log` |  | Show behavior and workflow run logs in terminal output |
| `--log-level` | <level:string> | Set log level (trace, debug, info, warning, error, fatal) |
| `-q, --quiet` |  | Suppress non-essential output |
| `-v, --verbose` |  | Show detailed output |
| `--no-telemetry` |  | Disable telemetry for this invocation |
| `--show-properties` |  | Show structured properties in log output |
| `--no-color` |  | Disable colored output |

## Common flags collapsed in the group files

| Flag | On commands | Description |
|---|---|---|
| `--repo-dir` | 168 | Repository directory (env: SWAMP_REPO_DIR) |
| `--ca-cert` | 147 | Path to PEM-encoded CA certificate to trust for TLS connections to the server (env: SWAMP_CA_CERT) |
| `--token-file` | 146 | Path to a file containing the server token; mutually exclusive with --token (env: SWAMP_SERVER_TOKEN_FILE, used only for the server named by --server, SWAMP_SERVE_URL or SWAMP_SERVER_URL) |
| `--token` | 133 | Server token in <name>.<secret> format; only applies with --server (overrides stored credentials and SWAMP_SERVER_TOKEN) |
| `--server` | 130 | Run through a 'swamp serve' server (ws:// or http://) instead of locally; no local repo required (env: SWAMP_SERVE_URL or SWAMP_SERVER_URL; in a checkout whose datastore is format 3, only this flag runs it on serve, and the env makes serve its datastore's upstream). For proxy/tunnel pass-through headers see SWAMP_SERVE_EXTRA_HEADERS. |
| `-y, --yes` | 18 | Skip confirmation prompt |
| `-f, --force` | 14 | Skip confirmation prompt (alias for --yes) |
| `--token` | 12 | Server token; only applies with --server (falls back to stored credential or SWAMP_SERVER_TOKEN) |

## Groups

| File | Root commands | Commands |
|---|---|---|
| access.md | access | 21 |
| agent.md | agent | 4 |
| behavior.md | behavior | 27 |
| data.md | data | 10 |
| datastore.md | datastore | 26 |
| extension.md | extension | 27 |
| operations.md | audit, doctor, run, summarise | 21 |
| report.md | report | 7 |
| serve.md | serve | 7 |
| setup.md | auth, completions, config, dashboard, inbox, init, invite, issue, quest, repo, source, start, subscription, telemetry, update, version, workspace | 55 |
| vault.md | vault | 17 |
| worker.md | worker | 14 |
| workflow.md | workflow | 33 |
