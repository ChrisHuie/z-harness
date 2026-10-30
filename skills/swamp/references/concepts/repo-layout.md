# Repository layout, behaviors, and the method lifecycle

## Layout

```text
.swamp.yaml                     repo marker and config (tracked)
models/<type>/<name>.yaml       behavior definitions (tracked; the directory keeps the legacy name)
workflows/*.yaml                workflow definitions (tracked)
vaults/<type>/<id>.yaml         vault configs, no secret values (tracked)
grants/*.yaml                   serve grants (tracked)
extensions/<kind>/              local extension sources plus their manifest (tracked)
./upstream_extensions.json      lockfile of pulled extensions (tracked)
tasks/<date>-<slug>.md          briefs written by swamp start
.swamp/                         runtime data (ignored): data/, auto-definitions/, secrets/, audit/,
                                workflows-evaluated/, pulled-extensions/, serve.yaml, serve.pid
.swamp-sources.yaml             local extension sources outside the repo (ignored)
~/.swamp/                       SWAMP_HOME: Deno runtime, workspaces, data dir
~/.config/swamp/                SWAMP_CONFIG_DIR: credentials, workspace registry
```

Agent scaffolding depends on `tools` in `.swamp.yaml`. For the `claude` tool: a managed section
in the repository's own CLAUDE.md, bundled skills in the home skills directory (refreshed by
`swamp update`, `swamp repo init` and `swamp repo upgrade`), extension skills under
`.claude/skills/`, and `.claude/settings.local.json` with an allowlist plus hooks that run
`swamp audit record`. Other built-in tools: `amp`, `cursor`, `kiro`, `opencode`, `codex`,
`copilot`, `pi`, `antigravity`; `none` skips scaffolding. Custom tools come from
`swamp agent setup`.

## Type versus definition

A behavior type is TypeScript (under `extensions/behaviors/`, legacy `extensions/models/`, or a
pulled extension) declaring global arguments, methods with input schemas, and output specs. A
definition is YAML binding a type to concrete values. Definition fields: `type`,
`typeVersion`, `id` (UUID assigned by `swamp behavior create`), `name`, `version`, `tags`,
`globalArguments`, `methods`, and optional `inputs` (a JSON-schema object the definition accepts
at run time), `checks` (pre-flight selection), `reports` (post-run selection), `resources`
(per-spec overrides: `lifetime`, `garbageCollection`, `tags`, `vaultName`, `vary`).

Never hand-write a definition or its `id`: `swamp behavior create <type> <name> --json`, then
edit. Never change `id`. `swamp behavior get <name> --json` reports staleness when the installed
type's `typeVersion` is newer; the type's `upgrades` entries migrate the definition on validate.

## Direct type execution

`swamp behavior run @<type> <method> <name> --input k=v` creates `<name>` under
`.swamp/auto-definitions/` when it does not exist. Auto-definitions are not git-tracked and do
not appear in `swamp behavior search`. Promote with `swamp behavior create` once the thing is
permanent. `command/shell` (`globalArgs.run`) is the escape hatch for one-off commands;
wrapping the same tool repeatedly is the signal to search for or write an extension type.

## Method lifecycle

Definition evaluation (CEL late-binding), then pre-flight checks (skipped for read and list
methods), then execution, then a versioned, immutable data write. `rollbackOnFailure` exists
only for local batch methods, never for external systems.

## Locking

One method run per behavior at a time. The default wait is 60 seconds (`SWAMP_LOCK_TIMEOUT_MS`);
`lock_timeout` exits 75. Inspect or break a stuck lock with `swamp datastore lock status` and
`swamp datastore lock release --force --behavior <type/name>`. Over serve in team mode,
`swamp behavior lease acquire <name> --for <5s..60m>` holds the lock across several commands.

## History versus output

`swamp behavior history` is the run record (status, timing, inputs). `swamp behavior output` is
what the run produced: the log artifact and the data artifacts. `swamp run history` spans
methods and workflows; `swamp run doctor --fix` reaps runs whose owner process died.
