verified: 2026-07-14 · sources: modes-and-composition §2/§6/§7 (stance table, enforcement, handoffs), concepts M3/M7/§4-security (C6)

# Stance: operate

**Job:** run and automate — execute scoped scripts/commands for CI and automation. Initiative I2 (act within scripts).

## Envelope
- **Tool posture:** exec-heavy but **scoped** — only the commands the job needs, not open-ended write.
- **Context gathering:** minimal — the job is defined; don't go exploring.
- **Policy blocks:** persistence (drive the run to completion) + scope-discipline. Escape hatch: on a blocking failure, report rather than improvise around it.
- **Verification:** logs and exit codes. Success is a clean exit with evidence, not an assertion.

## Output / handoff
A **run report**: exit codes, logs, outcomes. Consumes: the job spec (command/script + inputs). Sits **outside the dev pipeline** by design — it serves automation/CI and never transitions into implement without re-routing through the routing rules (modes §5).

## Routing — entering / leaving
- **Enter when:** the task is "run X" / "automate Y" against a defined script or CI step.
- **Leave when:** the run finishes → hand off the report. A finding that demands a code change re-routes (plan/implement), it is not silently actioned here.
- **Continuous re-routing:** a mid-session redirect re-routes immediately; acknowledge the switch. Explicit invocation is the top signal (M7); harness-enforced mode supersedes it (M3).

## Security (operate touches real systems)
**Irreversible / outward-facing operations (deploy, delete, send, pay, egress) require explicit approval.** Redact secrets — never echo credentials into logs, reports, or artifacts.

## Enforcement (scoped exec)
- **Claude Code:** `allowed-tools` scoped to the specific commands (e.g. `Bash(npm test:*)`); permission rules + hooks on destructive commands.
- **Codex:** `sandbox_mode` matched to the job (read-only vs. workspace-write) + approval policy for irreversible ops.
- **Fallback:** prose approval-gate clause on any destructive/outward-facing step.
