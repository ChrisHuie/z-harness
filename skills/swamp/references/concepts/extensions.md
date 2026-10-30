# Extensions and reports

## Layout and manifest

Sources live under `extensions/<kind>/` with a manifest. Manifest fields: `manifestVersion: 1`,
`name: "@collective/name"`, `version: YYYY.MM.DD.MICRO` (CalVer), lists of `behaviors` (or
`models`), `workflows`, `vaults`, `datastores`, `reports`, `webhooks`, `skills`,
`additionalFiles` (bare basenames), `include`, `binaries`, `platforms`, `labels`,
`dependencies`, `license` (SPDX), `repository`, `releaseNotes`, `visibility`,
`paths.base: typedDir|manifest`.

A behavior type file exports `behavior` (legacy `model`) with `type`, `name`, `description`,
`globalArgsSchema`, and `methods`, each with `inputSchema`, `outputs`, and `execute(context,
args)`. Schemas use `npm:zod@4`, which Swamp provides. The `context` offers `writeResource`,
`readResource`, `readModelData`, `queryData`, `createFileWriter`, `runModel` (needs declared
`dependencies`; unavailable on workers; depth 10, 100 calls), `logger`, `vaultService`,
`dataRepository`. Mark secret output fields sensitive in the schema metadata so they are
vaulted. `upgrades` entries migrate definitions when `typeVersion` changes.

Reports export `report` with `name`, `description`, `scope` (`method`, `workflow`, `model`) and
`execute(context)` returning `markdown` and `json`. They run automatically after method and
workflow runs; there is no run command. Filter with `--report`, `--report-label`,
`--skip-report`, `--skip-report-label`, `--skip-reports` on `swamp behavior run` and
`swamp workflow run`; a workflow pins them under `reports: { require, skip }`. Read results with
`swamp report search` and `swamp report get <name> --behavior <def>` or `--workflow <wf>`.

Extensions run in Deno under the swamp home directory; `swamp doctor extensions --json`
reports the binary path for running sibling tests.

## Publishing pipeline

```bash
swamp auth whoami
swamp extension version --manifest extensions/<kind>/manifest.yaml
swamp extension fmt extensions/<kind>/manifest.yaml
swamp extension quality extensions/<kind>/manifest.yaml       # --isolated to match the registry's cache
swamp extension push extensions/<kind>/manifest.yaml --dry-run --json
swamp extension push extensions/<kind>/manifest.yaml --channel beta
swamp extension promote @collective/name <version> --channel stable
```

Scorecard rubric v6 has 16 points; `repository-verified` is provisional locally, so the local
maximum is 14 of 16. Review warnings to expect: `testing-completeness` (a sibling `_test.ts`),
`adversarial-review-report` (a JSON skeleton from `--dry-run --json`), `behavior-spelling`,
`credentials-sensitive-field`, `schema-strictness`, `bare-specifiers`. Accept a rule with a
`// swamp-quality-ignore <rule>: <reason>` comment or a quality file beside the manifest.
Dependencies are checked against OSV.dev, npm and JSR; pin exact versions or commit a lock.
Limits: 150 files, 1 MB per file, 10 MB total; allowed extensions ts, json, md, yaml, yml, txt.
Channels: `beta`, `rc`, `stable`; `yank` and `deprecate` are reversible with `unyank` and
`undeprecate`.

## Consuming

`swamp extension search`, `info`, `pull <name>[@version] [--channel]`, `install` (restore the
lockfile after a clone or in CI), `list`, `update [--check]`, `outdated` (exits 1 when behind),
`rm`. Only the `swamp` collective is trusted by default; `swamp extension trust add
<collective>` or `trust auto-trust enable` widens it. A trusted collective's extensions still pin
to the lockfile's version and checksum. `swamp extension source add <path> [--only kinds]`
registers local sources outside the repository.
