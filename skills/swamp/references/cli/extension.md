# swamp CLI: extension
Generated from `swamp help --json`, swamp 20261030.195233.0-sha.713d92e4. Do not edit by hand; regenerate with `python3 scripts/render_cli_reference.py`.

Root commands in this group: extension.

## swamp extension

Manage swamp extensions

## swamp extension push

Push an extension to the swamp registry

Arguments: manifest-path  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--extensions-dir` | <dir:string> | Extensions root: the directory that contains extensions/ (behaviors, workflows and skills resolve from it; env: SWAMP_EXTENSIONS_DIR) |
| `-y, --yes` |  | Skip confirmation prompts; the summary records any warnings this waived |
| `-f, --force` |  | Skip confirmation prompts (alias for --yes) |
| `--dry-run` |  | Build the archive and run the registry checks read-only, without pushing |
| `--visibility` | <visibility:string> | Publication visibility: public (registry default) or private; overrides manifest visibility. Omit to use the manifest or registry default. |
| `--release-notes` | <text:string> | Per-version release notes (max 5000 chars) |
| `--channel` | <channel:string> | Release channel: 'beta', 'rc', or 'stable' (default: stable) |
| `--version-suffix` | <type:string> | Override version micro segment: 'epoch' uses Unix timestamp (e.g. 2026.06.18.1750263600) |
| `--skip-upgrade-check` |  | Suppress warning when version is bumped without upgrade entries |

Common flags (see index.md): `--repo-dir`

## swamp extension info

Show full registry metadata for a specific extension

Arguments: name  (`?` marks optional)

Common flags (see index.md): `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp extension fmt

Format and lint extension TypeScript files

Arguments: manifest-path  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--extensions-dir` | <dir:string> | Extensions root: the directory that contains extensions/ (behaviors, workflows and skills resolve from it; env: SWAMP_EXTENSIONS_DIR) |
| `--check` |  | Check only, do not auto-fix |

Common flags (see index.md): `--repo-dir`

## swamp extension quality

Score an extension against the Swamp Club quality rubric (10 client-earnable factors) and cache the packaged tarball for reuse by push

Arguments: manifest-path  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--extensions-dir` | <dir:string> | Extensions root: the directory that contains extensions/ (behaviors, workflows and skills resolve from it; env: SWAMP_EXTENSIONS_DIR) |
| `--isolated` |  | Run deno doc as the registry does: an empty dependency cache and no registry tokens or npm config from the environment. Slower; use it when a private import or a warm cache could make the local score differ from the registry's |

Common flags (see index.md): `--repo-dir`

## swamp extension pull

Pull an extension from the swamp registry

Arguments: extension  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `-y, --yes` |  | Overwrite existing files without prompting |
| `--force` |  | Overwrite existing files without prompting (alias for --yes) |
| `--channel` | <channel:string> | Release channel: 'beta', 'rc', or 'stable' (default: stable) |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp extension install

```text
Restore pulled extensions from the lockfile.

Reads upstream_extensions.json and re-pulls any extension whose source
files are missing, whose content has drifted, or whose installed version
does not match the pinned one. Use after cloning a repo or in CI.
To add a new extension, use 'swamp extension pull <name>' instead.
```

Arguments: unexpected?  (`?` marks optional)

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp extension rm (alias: remove)

Remove a pulled extension, its files, and its lockfile entry

Arguments: extension  (`?` marks optional)

Common flags (see index.md): `--repo-dir`, `-y, --yes`, `-f, --force`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp extension list (alias: ls)

List upstream installed extensions

| Flag | Value | Description |
|---|---|---|
| `--check-updates` |  | Check the registry for newer versions and show a 'latest' column. Runs by default when stdout is a terminal; pass this flag to force on (e.g. when using --json in CI). |
| `--no-check-updates` |  | Skip the registry check for newer versions, showing only installed data. |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp extension search

Search the swamp extension registry

Arguments: query?  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--collective` | <collective:string> | Filter by collective |
| `--platform` | <platform:string> | Filter by a platform the extension declares (e.g. linux-x86_64) |
| `--label` | <label:string> | Filter by label |
| `--content-type` | <contentType:string> | Filter by content type (behaviors or models, workflows, vaults, datastores, reports) |
| `--sort` | <sort:string> | Sort order: relevance, new, updated, name |
| `--channel` | <channel:string> | Filter by release channel: 'beta', 'rc', or 'stable' (default: stable only) |
| `--per-page` | <perPage:number> | Results per page Default: 20. |
| `--page` | <page:number> | Page number Default: 1. |
| `--licensed` |  | Only list extensions that declare a license |

Common flags (see index.md): `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp extension update

Update installed extensions to latest versions

Arguments: extension?  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--check` |  | Show what's outdated without pulling |

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp extension outdated

List installed extensions with newer versions available. Exits 1 if any update is available (suitable for CI gates).

Common flags (see index.md): `--repo-dir`, `--server`, `--token`, `--token-file`, `--ca-cert`

## swamp extension version

Show the latest published version and compute the next CalVer version for an extension

Arguments: name?  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--manifest` | <path:string> | Read extension name from a manifest.yaml file |

## swamp extension yank

Yank an extension or specific version from the registry. Use `swamp extension unyank` to reverse.

Arguments: extension, version?  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--reason` | <reason:string> | Reason for yanking |
| `--channel` | <channel:string> | Release channel to yank: 'stable', 'beta', or 'rc' (default: all channels) |

Common flags (see index.md): `-y, --yes`, `-f, --force`

## swamp extension unyank

Unyank an extension or specific version, restoring availability

Arguments: extension, version?  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--reason` | <reason:string> | Optional reason (audit log only) |
| `--channel` | <channel:string> | Release channel to unyank: 'stable', 'beta', or 'rc' (default: all channels) |

Common flags (see index.md): `-y, --yes`, `-f, --force`

## swamp extension deprecate

Deprecate an extension in the registry. Use `swamp extension undeprecate` to reverse.

Arguments: extension  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--reason` | <reason:string> | Reason for deprecation |
| `--superseded-by` | <extension:string> | Extension that supersedes this one |

Common flags (see index.md): `-y, --yes`, `-f, --force`

## swamp extension undeprecate

Remove the deprecation status from an extension in the registry.

Arguments: extension  (`?` marks optional)

Common flags (see index.md): `-y, --yes`, `-f, --force`

## swamp extension trust

Manage trusted collectives for extension auto-resolution

## swamp extension trust list

List trusted collectives for extension auto-resolution

Common flags (see index.md): `--repo-dir`

## swamp extension trust add

Add a collective to the trusted list

Arguments: collective  (`?` marks optional)

Common flags (see index.md): `--repo-dir`

## swamp extension trust rm

Remove a collective from the trusted list

Arguments: collective  (`?` marks optional)

Common flags (see index.md): `--repo-dir`

## swamp extension trust auto-trust

Enable or disable auto-trusting membership collectives

Arguments: enabled  (`?` marks optional)

Common flags (see index.md): `--repo-dir`

## swamp extension source

Manage local extension sources

## swamp extension source list

List configured extension sources

Common flags (see index.md): `--repo-dir`

## swamp extension source add

Add a local extension source (standard or direct-content layout).

Arguments: path  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--only` | <types:string> | Only load these extension types (comma-separated: behaviors or models,vaults,datastores,reports,webhooks,workflows) |

Common flags (see index.md): `--repo-dir`

## swamp extension source rm

Remove a local extension source

Arguments: path  (`?` marks optional)

Common flags (see index.md): `--repo-dir`

## swamp extension promote

Promote an extension version to a higher release channel (beta→rc, beta→stable, rc→stable), by name and version or from a manifest path

Arguments: extension-or-manifest, version?  (`?` marks optional)

| Flag | Value | Description |
|---|---|---|
| `--channel` | <channel:string> | Target channel to promote to: 'rc' or 'stable' |
| `--from-channel` | <fromChannel:string> | Source channel ('beta' or 'rc'); skips direction validation if omitted |
| `--repo-dir` | <dir:string> | Repository directory a relative manifest path resolves against (env: SWAMP_REPO_DIR) |
| `--extensions-dir` | <dir:string> | Extensions root a relative manifest path resolves against (env: SWAMP_EXTENSIONS_DIR) |
