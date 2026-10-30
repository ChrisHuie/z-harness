# Where the CLI, the manual and the bundled guides disagree

The installed CLI's schema (`swamp help --json`) is the authority for what a command accepts;
the manual at swamp-club.com/manual is the authority for what it must do; the bundled Swamp Club
skill under assets/upstream/ is procedure. Each row names the evidence and how to re-check it.
Regenerate references/cli/ after a CLI update and re-read this table against it.

| Topic | What the schema shows | What the other source says | Re-check with |
|---|---|---|---|
| `swamp audit` | A hidden root command with subcommands `record`, `alerts`, `export`, `log`, `report`, `rotate-key`, `verify` | Omitted from `swamp help` and from the top-level schema because it is hidden; the manual documents `swamp audit [--hours] [--all] [--session]` | `swamp help audit --json` |
| `swamp report run` | No such command; `swamp report` has `type search`, `search`, `get`, `describe`, `list` | The bundled skill's hub lists `swamp report run <name>` | `swamp report run` is refused as not a subcommand of `report` |
| `swamp vault status` | No such command | The bundled extension vault troubleshooting pages name it | `swamp vault status` is refused as not a subcommand of `vault`; use `swamp vault get <name> --json` or `swamp doctor vaults` |
| Workflow task types | The schema from `swamp workflow schema get` has six task shapes: `behavior`, `model_method`, `workflow`, `manual_approval`, `assert`, `wait_for_signal` | The bundled workflow reference says four; the manual's workflows reference documents four and omits `wait_for_signal` | `swamp workflow schema get --json` |
| `wait_for_signal` fields | `key`, `schema` (JSON-schema object), `timeout` (seconds, at most one year), `acceptEarly` (seconds, at most one hour) | Not in the manual's workflows reference; `swamp workflow signal` and `waits` exist in the CLI | `swamp workflow schema get --json` |
| `swamp workflow run --detach` | Present; returns the run id once the server started the run; requires `--server` | The manual's workflows reference says the CLI has no detached mode | `swamp help workflow run --json` |
| `swamp data get` | Present but deprecated; each read prints the equivalent `swamp data query` | Older guides use it as the read path | `swamp help data get` |
| `swamp datastore setup s3` | Present as a removed stub that points at `setup extension @swamp/s3-datastore` | Older material shows it as the S3 path | `swamp help datastore setup s3` |
| `swamp serve --detach-runs` | Accepted and ignored; HA mode is detected from the datastore | Older material presents it as the switch | `swamp help serve --json` |
| `--force` versus `--yes` | On `behavior delete`, `vault remove`, `vault delete`, `datastore lock release` and `init`, `--force` carries extra meaning and is not a plain alias of `--yes` | Most other commands document `--force` as the alias | the flag table of each command in references/cli/ |

A row whose re-check no longer reproduces is stale: delete it in the same change that
regenerates the reference.
