# swamp CLI: access
Generated from `swamp help --json`, swamp 20261030.195233.0-sha.713d92e4. Do not edit by hand; regenerate with `python3 scripts/render_cli_reference.py`.

Root commands in this group: access.

## swamp access

Manage authorization policies (grants), groups, and access checks

## swamp access token

Manage server tokens for user authentication

## swamp access token mint

Mint a server token for user authentication

Arguments: name  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--principal` | <principal:string> | Principal identity for the token: user:<id> or worker:<id> (e.g. user:adam) |
| `--email` | <email:string> | Display email for the token holder (defaults to principal) |
| `--duration` | <duration:string> | Token lifetime (e.g. 30m, 1h, 24h, 7d, 30d) Default: 30d. |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp access token list

List server tokens: state, principal, expiry, and last use

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp access token reveal

Show the full authentication credential for a server token

Arguments: name  (`?` marks optional)

Common flags (see index.md): `--repo-dir`, `-y, --yes`, `-f, --force`

## swamp access token revoke

Invalidate a server token before it expires

Arguments: name  (`?` marks optional)

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp access token rotate

Revoke an existing token and mint a replacement with the same name and principal

Arguments: name  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--duration` | <duration:string> | Lifetime for the new token (e.g. 30m, 1h, 24h, 7d, 30d) Default: 30d. |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp access grant (alias: policy)

Manage authorization grants

## swamp access grant create

Create a new authorization grant

| Flag | Value | Description |
|---|---|---|
| `--subject` | <subject:string> | Grant subject (e.g. user:adam, group:release-managers, idp-group:platform-eng) |
| `--allow` | <actions:string> | Actions to allow (comma-separated) |
| `--deny` | <actions:string> | Actions to deny (comma-separated) |
| `--on` | <resource:string> | Resource selector (e.g. workflow:@acme/*, behavior:@acme/deploy) |
| `--when` | <condition:string> | Optional CEL condition |
| `--methods` | <methods:string> | Restrict to specific methods (comma-separated, e.g. read,list) |
| `--server` | <url:string> | Run through a 'swamp serve' server instead of locally (env: SWAMP_SERVE_URL) |

Common flags (see index.md): `--repo-dir`, `--token`, `--token-file`, `--ca-cert`

## swamp access grant list

List authorization grants

| Flag | Value | Description |
|---|---|---|
| `--subject` | <subject:string> | Filter by subject |
| `--on` | <resource:string> | Filter by resource selector (exact match) |
| `--server` | <url:string> | List grants on a 'swamp serve' server instead of locally (env: SWAMP_SERVE_URL) |

Common flags (see index.md): `--repo-dir`, `--token`, `--token-file`, `--ca-cert`

## swamp access grant revoke

Revoke an authorization grant

Arguments: grant_id  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--server` | <url:string> | Revoke a grant on a 'swamp serve' server instead of locally (env: SWAMP_SERVE_URL) |

Common flags (see index.md): `--repo-dir`, `--token`, `--token-file`, `--ca-cert`

## swamp access group

Manage local groups

## swamp access group create

Create a local group

Arguments: name  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--server` | <url:string> | Create a group on a 'swamp serve' server instead of locally (env: SWAMP_SERVE_URL) |

Common flags (see index.md): `--repo-dir`, `--token`, `--token-file`, `--ca-cert`

## swamp access group add-member

Add a principal to a group

Arguments: group, principal  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--server` | <url:string> | Add a member on a 'swamp serve' server instead of locally (env: SWAMP_SERVE_URL) |

Common flags (see index.md): `--repo-dir`, `--token`, `--token-file`, `--ca-cert`

## swamp access group remove-member

Remove a principal from a group

Arguments: group, principal  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--server` | <url:string> | Remove a member on a 'swamp serve' server instead of locally (env: SWAMP_SERVE_URL) |

Common flags (see index.md): `--repo-dir`, `--token`, `--token-file`, `--ca-cert`

## swamp access group list

List all groups

| Flag | Value | Description |
|---|---|---|
| `--server` | <url:string> | List groups on a 'swamp serve' server instead of locally (env: SWAMP_SERVE_URL) |

Common flags (see index.md): `--repo-dir`, `--token`, `--token-file`, `--ca-cert`

## swamp access group list-idp

List IdP groups observed from authenticated users on a server

| Flag | Value | Description |
|---|---|---|
| `--server` | <url:string> | Server to query (required; env: SWAMP_SERVE_URL) |
| `--token` | <token:string> | Server token (falls back to stored credential or SWAMP_SERVER_TOKEN) |

Common flags (see index.md): `--token-file`, `--ca-cert`

## swamp access group members

List members of a group

Arguments: name  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--server` | <url:string> | List members on a 'swamp serve' server instead of locally (env: SWAMP_SERVE_URL) |

Common flags (see index.md): `--repo-dir`, `--token`, `--token-file`, `--ca-cert`

## swamp access can-i

Check your own permissions against the server's grants

| Flag | Value | Description |
|---|---|---|
| `--server` | <url:string> | Server to check permissions against (env: SWAMP_SERVE_URL) |
| `--action` | <action:string> | Action to check (run, read, write, approve, signal, tag, admin) |
| `--on` | <resource:string> | Resource to check (e.g. workflow:@acme/deploy) |
| `--method` | <method:string> | Method name to check (e.g. read, create) — used with method-scoped grants |

Common flags (see index.md): `--token`, `--token-file`, `--ca-cert`

## swamp access check

Explain whether a subject can perform an action on a resource

| Flag | Value | Description |
|---|---|---|
| `--subject` | <subject:string> | Subject to check (e.g. user:adam) |
| `--action` | <action:string> | Action to check (run, read, write, approve, signal, tag, admin) |
| `--on` | <resource:string> | Resource to check (e.g. workflow:@acme/deploy) |
| `--collectives` | <collectives:string> | Comma-separated collective memberships for CEL condition evaluation (principal.collectives); use --groups to simulate idp-group: grant subjects |
| `--groups` | <groups:string> | Comma-separated IdP group memberships to simulate for idp-group: grants |
| `--field` | <field:string> | Resource field for condition evaluation (key=value, repeatable); overrides the field resolved from the repo |
| `--server` | <url:string> | Check access on a 'swamp serve' server instead of locally (env: SWAMP_SERVE_URL) |

Common flags (see index.md): `--repo-dir`, `--token`, `--token-file`, `--ca-cert`

## swamp access reload

Rebuild the policy snapshot from current grants and groups

| Flag | Value | Description |
|---|---|---|
| `--server` | <url:string> | Reload access policy on a 'swamp serve' server instead of locally (env: SWAMP_SERVE_URL) |

Common flags (see index.md): `--repo-dir`, `--token`, `--token-file`, `--ca-cert`
