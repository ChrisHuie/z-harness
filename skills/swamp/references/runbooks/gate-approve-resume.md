# Runbook: gate a workflow on manual approval

1. Add a step with `task: { type: manual_approval, prompt: "<question>", timeout: 3600 }` and
   make the sensitive step depend on it with `condition: { type: succeeded }`.
2. `swamp workflow validate <name>`, then `swamp workflow run <name>`. The run exits when it
   suspends; the output names the gate.
3. `swamp workflow approvals` lists suspended runs still inside their window; an expired gate
   no longer appears and cannot be approved.
4. Decide: `swamp workflow approve <name> <step> [--run <id>] --reason "<why>"` or
   `swamp workflow reject <name> <step> --reason "<why>"`. Approval records a decision only.
5. Continue: `swamp workflow resume <name> [--run <id>]`. Add inputs the rest of the run needs
   with `--input k=v`; they merge over the original inputs and are persisted, so a secret goes
   into a vault first (`swamp vault put`) and only its key name is passed.
6. Under `swamp serve`, approving through the server (`--server`, or the dashboard) resumes the
   run itself only when auto-resume applies: `autoResume: true` on the workflow, or no declared
   inputs with serve started with `--auto-resume`. A local approve never does.
7. A gate inside a nested workflow is approved under the child's own name and run id;
   `swamp workflow approvals` names the parent.

Separation of duties: `approve` and `reject` check the `approve` action. With the default
grants `run` implies `approve`; start serve with `--approve-requires-explicit-grant` to require
a dedicated approver grant.
