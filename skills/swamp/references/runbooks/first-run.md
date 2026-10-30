# Runbook: first run of a behavior type and reading what it wrote

Use for a new repository, a `swamp start` brief, or a type you have not run before.

1. Confirm sign-in and the repository: `swamp auth whoami --json`; a missing `.swamp.yaml`
   means `swamp repo init` (the brief path has already done both).
2. Find the type, stopping at the first match: `swamp behavior type search <keywords> --json`,
   then `swamp extension search <keywords> --json` for `@swamp/*` and other collectives, then
   extend an existing type, then a custom extension (assets/upstream/references/extension/guide.md).
   `command/shell` only for a genuine one-off.
3. Read the type: `swamp behavior type describe <type> --compact --json`. Pick a read method
   for a first run (`get`, `list`, `describe`, `lookup`), not `sync`, which fails with no state.
4. Run it. One-off: `swamp behavior run @<type> <method> <name> --input k=v --json`.
   Permanent: `swamp behavior create <type> <name> --json`, edit the scaffold, then
   `swamp behavior validate <name> --method <method>` and `swamp behavior run <name> <method>`.
   If the method touches a real account, cluster or project, confirm the target with the user
   before running.
5. Read the output: `swamp data list <name>`, then
   `swamp data query 'behavior("<name>") && isLatest' --select '{"n": name, "a": attributes}'`.
   Logs: `swamp behavior history search <name>` and `swamp behavior history logs <output id>`.
6. Report the exit code, the data names written, and the CEL path another behavior would use:
   `${{ data.latest("<name>", "<data name>").attributes.<field> }}`.

Failure: load assets/upstream/references/troubleshooting/guide.md before retrying or editing
the definition; `swamp behavior output logs <output id> --tail 50` shows the method's own log.
