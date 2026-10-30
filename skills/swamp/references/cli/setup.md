# swamp CLI: setup
Generated from `swamp help --json`, swamp 20261030.195233.0-sha.713d92e4. Do not edit by hand; regenerate with `python3 scripts/render_cli_reference.py`.

Root commands in this group: auth, completions, config, dashboard, inbox, init, invite, issue, quest, repo, source, start, subscription, telemetry, update, version, workspace.

## swamp version

Display the version of swamp

Common flags (see index.md): `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp init

Initialize a new swamp repository

Arguments: path?  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `-f, --force` |  | Reinitialize if already exists (not an alias for --yes) |
| `-t, --tool` | <tool:toolName> | AI coding tool to configure for. Repeat to enroll multiple tools (e.g. `--tool claude --tool kiro`). Duplicates are collapsed. Use `--tool none` (alone) to skip tool scaffolding. Defaults to `claude` when omitted. Built-in: amp, claude, cursor, kiro, opencode, codex, copilot, pi, antigravity, none. Custom tools defined via `swamp agent setup` are also accepted. |
| `--no-vault` |  | Skip creating the default vault. By default init creates a local_encryption vault named `default` and records it as `defaultVault` in .swamp.yaml |
| `--server` | <url:string> | Default serve URL for this repository — stored in .swamp.yaml as serverAddress (env: SWAMP_SERVE_URL overrides at runtime). A URL with credentials, a query string or a fragment is refused — give remote commands the token with --token, or store it with swamp auth server-login |

## swamp repo

Manage swamp repositories

## swamp repo init

Initialize a new swamp repository

Arguments: path?  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `-f, --force` |  | Reinitialize if already exists (not an alias for --yes) |
| `-t, --tool` | <tool:toolName> | AI coding tool to configure for. Repeat to enroll multiple tools (e.g. `--tool claude --tool kiro`). Duplicates are collapsed. Use `--tool none` (alone) to skip tool scaffolding. Defaults to `claude` when omitted. Built-in: amp, claude, cursor, kiro, opencode, codex, copilot, pi, antigravity, none. Custom tools defined via `swamp agent setup` are also accepted. |
| `--no-vault` |  | Skip creating the default vault. By default init creates a local_encryption vault named `default` and records it as `defaultVault` in .swamp.yaml |
| `--server` | <url:string> | Default serve URL for this repository — stored in .swamp.yaml as serverAddress (env: SWAMP_SERVE_URL overrides at runtime). A URL with credentials, a query string or a fragment is refused — give remote commands the token with --token, or store it with swamp auth server-login |

## swamp repo upgrade

Upgrade an existing swamp repository

Arguments: path?  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `-t, --tool` | <tool:toolName> | Replace the enrolled tool list. Repeat to enroll multiple tools (e.g. `--tool claude --tool kiro`). Omit to preserve the existing list and just bump the swamp version. `--tool none` clears. |
| `--include-gitignore` |  | Manage a swamp section in .gitignore |

## swamp telemetry

Manage CLI telemetry

## swamp telemetry stats

View telemetry usage statistics

| Flag | Value | Description |
|---|---|---|
| `--days` | <days:number> | Number of days to analyze Default: 2. |

## swamp update

Update swamp to the latest version

| Flag | Value | Description |
|---|---|---|
| `--check` |  | Check for updates without installing |
| `--setup-auto` | [action:string] | Configure autoupdate interactively; use 'status' to check, 'disable' to turn off |

## swamp config

Manage swamp configuration

## swamp config get

Get a configuration value

Arguments: key  (`?` marks optional)

## swamp config set

Set a configuration value

Arguments: key, value  (`?` marks optional)

## swamp config list

List all configuration keys and current values

## swamp source

Manage swamp source code for troubleshooting

## swamp source fetch

Download swamp source code from GitHub

## swamp source path

Show swamp source location and version

## swamp source clean

Remove downloaded swamp source

## swamp completions

```text
Generate shell completions.

To enable shell completions for this program add the following line to your ~/.bashrc or similar:

    source <(swamp completions [shell])

    For more information run swamp completions [shell] --help
```

## swamp completions bash

```text
Generate shell completions for bash.

To enable bash completions for this program add following line to your ~/.bashrc:

    source <(swamp completions bash)
```

| Flag | Value | Description |
|---|---|---|
| `-n, --name` | <command-name> | The name of the main command. |

## swamp completions fish

```text
Generate shell completions for fish.

To enable fish completions for this program add following line to your ~/.config/fish/config.fish:

    source (swamp completions fish | psub)
```

| Flag | Value | Description |
|---|---|---|
| `-n, --name` | <command-name> | The name of the main command. |

## swamp completions zsh

```text
Generate shell completions for zsh.

To enable zsh completions for this program add following line to your ~/.zshrc:

    source <(swamp completions zsh)
```

| Flag | Value | Description |
|---|---|---|
| `-n, --name` | <command-name> | The name of the main command. |

## swamp completions powershell

```text
Generate shell completions for PowerShell.

To enable PowerShell completions for this program add the following line to your PowerShell profile:

    swamp completions powershell | Out-String | Invoke-Expression
```

| Flag | Value | Description |
|---|---|---|
| `-n, --name` | <command-name:string> | The name of the main command. |

## swamp issue

Search, fetch, report, and comment on swamp-club Lab issues

## swamp issue search

Search or list swamp-club Lab issues

Arguments: query?  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--type` | <type:string> | Filter by issue type (bug, feature, security, platform) |
| `--status` | <status:string> | Filter by status (open, triaged, in_progress, shipped, closed) |
| `--source` | <source:string> | Filter by source tag |
| `--limit` | <limit:integer> | Maximum number of results to return |

## swamp issue get

Fetch and display details of a swamp-club Lab issue

Arguments: number  (`?` marks optional)

## swamp issue edit

Edit the title, body, or type of an existing swamp-club Lab issue

Arguments: number  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `-t, --title` | <title:string> | New title (skips editor for title) |
| `-b, --body` | <body:string> | New body (requires --title, skips editor entirely) |
| `--type` | <type:string> | Change issue type (bug, feature, or security); escalating to security restricts visibility and cannot be reversed by non-admins |
| `--no-redact` |  | Skip automatic redaction of sensitive content (use when the content is deliberately sanitized) |

## swamp issue bug

Submit a bug report

| Flag | Value | Description |
|---|---|---|
| `-t, --title` | <title:string> | Bug title (with --body, skips the editor) |
| `-b, --body` | <body:string> | Bug description (requires --title, skips editor entirely) |
| `-e, --email` |  | Open email client with pre-filled bug report |
| `-x, --extension` | <name:string> | Route the bug against a specific extension (e.g. @adam/cfgmgmt) |
| `--repo-dir` | <dir:string> | Repository directory (env: SWAMP_REPO_DIR) — only used with --extension |
| `--no-redact` |  | Skip automatic redaction of sensitive content (use when the content is deliberately sanitized) |

## swamp issue feature

Submit a feature request

| Flag | Value | Description |
|---|---|---|
| `-t, --title` | <title:string> | Feature title (with --body, skips the editor) |
| `-b, --body` | <body:string> | Feature description (requires --title, skips editor entirely) |
| `-e, --email` |  | Open email client with pre-filled feature request |
| `-x, --extension` | <name:string> | Route the feature against a specific extension (e.g. @adam/cfgmgmt) |
| `--repo-dir` | <dir:string> | Repository directory (env: SWAMP_REPO_DIR) — only used with --extension |
| `--no-redact` |  | Skip automatic redaction of sensitive content (use when the content is deliberately sanitized) |

## swamp issue security

Submit a security vulnerability report (visible only to you and admins)

| Flag | Value | Description |
|---|---|---|
| `-t, --title` | <title:string> | Vulnerability title (with --body, skips the editor) |
| `-b, --body` | <body:string> | Vulnerability description (requires --title, skips editor entirely) |
| `-e, --email` |  | Open email client with pre-filled security report |
| `-x, --extension` | <name:string> | Route the security report against a specific extension (e.g. @adam/cfgmgmt) |
| `--repo-dir` | <dir:string> | Repository directory (env: SWAMP_REPO_DIR) — only used with --extension |
| `--no-redact` |  | Skip automatic redaction of sensitive content (use when the content is deliberately sanitized) |

## swamp issue ripple (alias: comment)

Post a ripple (comment) on an existing swamp-club Lab issue

Arguments: number  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `-b, --body` | <body:string> | Ripple body (skips editor) |
| `--close` |  | Close the issue after posting the ripple |
| `--reopen` |  | Reopen the issue after posting the ripple |
| `--no-redact` |  | Skip automatic redaction of sensitive content (use when the content is deliberately sanitized) |

## swamp invite

Invite people to swamp-club

## swamp invite link

Print your swamp-club invite link

## swamp auth

```text
Manage swamp-club authentication.

For non-interactive use, set the SWAMP_API_KEY environment variable.
```

## swamp auth login

```text
Authenticate with a swamp-club server.

For non-interactive use (CI, agents, scripts), set the SWAMP_API_KEY
environment variable (or SWAMP_API_KEY_FILE, a path to a file holding
the key) instead of running this command.
```

| Flag | Value | Description |
|---|---|---|
| `--club, --server` | <url:string> | swamp-club URL to sign in to (env: SWAMP_CLUB_URL; --server: kept older spelling, not 'swamp serve') |
| `--username` | <username:string> | Username or email |
| `--password` | <password:string> | Password (omit to prompt) |
| `--no-browser` |  | Disable browser login, use username/password |

## swamp auth logout

```text
Revoke the stored API key and remove stored credentials.

If the key cannot be revoked on the server, the credentials are kept.
```

## swamp auth whoami (alias: status)

```text
Show current authenticated identity.

serverUrl: the swamp-club site you are signed in to (SWAMP_CLUB_URL, set with 'swamp auth login --club').
effectiveServeUrl (Serve: in log output): the 'swamp serve' orchestrator SWAMP_SERVE_URL or SWAMP_SERVER_URL routes commands to, when set.
```

## swamp auth server-login

Authenticate with a swamp serve instance — uses OAuth device flow when available, or store a static token with --token

| Flag | Value | Description |
|---|---|---|
| `--server` | <url:string> | Server URL to authenticate with (env: SWAMP_SERVE_URL) |
| `--token` | <token:string> | Server token in <name>.<secret> format (skips OAuth flow) |

Common flags (see index.md): `--ca-cert`

## swamp auth token

Manage collective API tokens

## swamp auth token create

Create a scoped API token for a collective

| Flag | Value | Description |
|---|---|---|
| `--collective` | <collective:string> | Collective slug to create the token for |
| `--scopes` | <scopes:string> | Comma-separated scopes to grant (e.g. extensions:push,serve:*) |
| `--name` | <name:string> | Token label (default: cli-<hostname>-<timestamp>) |

## swamp auth token list

List API tokens for a collective

| Flag | Value | Description |
|---|---|---|
| `--collective` | <collective:string> | Collective slug to list tokens for |

## swamp auth token revoke

Revoke an API token for a collective

Arguments: token-id  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--collective` | <collective:string> | Collective slug the token belongs to |

## swamp quest

What treasures are there yet to discover?

| Flag | Value | Description |
|---|---|---|
| `--full` |  | Show every deed — including completed and not-yet-started — not just the ones in progress. |

## swamp subscription

Show the plan and billing standing of your swamp-club collectives, and open their billing page

## swamp subscription status

Show the plan and billing standing of the signed-in user and each collective they belong to, and how to open swamp-club billing.

## swamp subscription start

Open the swamp-club billing page in your browser to upgrade or manage billing, for yourself or a collective.

| Flag | Value | Description |
|---|---|---|
| `--collective` | <slug:string> | Open this collective's billing page instead of your own |
| `--no-browser` |  | Print the URL instead of opening a browser |

## swamp inbox

Browse your Swamp Club inbox. In a terminal, an interactive inbox where opening a message marks it read. Otherwise a list of messages with their ids, which marks nothing read.

| Flag | Value | Description |
|---|---|---|
| `--all` |  | Include messages you have already read; the interactive inbox always includes them |
| `--limit` | <n:integer> | How many messages to load, 1 to 100 (default 20) |
| `--before` | <id:string> | Load the messages older than this message id |

## swamp inbox read

Print one message and mark it read: the message with that id, or else the next one to read. Never interactive.

Arguments: message_id?  (`?` marks optional)

## swamp start

```text
Get from a task to an agent working on it. Opens a local page where you
pick or create a workspace, describe the task, sign in if needed and
pick an agent; Swamp then opens the agent in a new terminal window.
With --json it only reports your workspaces and agents; it starts
nothing and changes nothing.
```

| Flag | Value | Description |
|---|---|---|
| `--no-browser` |  | Print the URL instead of opening a browser |
| `--workspace` | <name:string> | Open this registered workspace, wherever its folder is, instead of choosing one in the browser; a new name is created in --path, else in the folder set with `swamp config set workspaces.dir`, else under the swamp data dir. With --json nothing is created |
| `--path` | <dir:string> | Create a new --workspace in <dir>/<name>; <dir> must already exist |

## swamp start status

Show your swamp start workspaces and which agents are on your PATH

| Flag | Value | Description |
|---|---|---|
| `--workspace` | <name:string> | Show only this workspace |

## swamp dashboard

```text
Open this repo's dashboard in your browser, with no swamp serve
running. It shows only this repo and does not add it to your
swamp start workspaces.
```

| Flag | Value | Description |
|---|---|---|
| `--repo-dir` | <dir:string> | Repository directory |
| `--no-browser` |  | Print the URL instead of opening a browser |

## swamp workspace

Manage workspaces: swamp repos Swamp keeps track of, wherever they are

## swamp workspace create

```text
Create a workspace: a new swamp repo with no agent set up
It goes in <name> under --path, else under the folder set with
`swamp config set workspaces.dir`, else under the swamp data dir
```

Arguments: name  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--path` | <dir:string> | Create the workspace in <dir>/<name>; <dir> must already exist |

## swamp workspace import

Register an existing swamp repo as a workspace, where it is. Nothing is moved or copied

Arguments: path  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--name` | <name:string> | Workspace name (default: made from the folder's name) |

## swamp workspace list

List registered workspaces

## swamp workspace get

Show one workspace

Arguments: name  (`?` marks optional)

## swamp workspace remove

Remove a workspace from the list. Its folder is kept; import it to bring it back

Arguments: name  (`?` marks optional)
