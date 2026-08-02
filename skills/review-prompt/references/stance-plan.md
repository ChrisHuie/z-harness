verified: 2026-07-14 · sources: modes-and-composition §2/§5/§6/§7/§9 (stance table, routing, enforcement, handoffs), concepts M3/M7 (C6)

# Stance: plan

**Job:** decide *what* to do and get sign-off before code. Initiative I1 (propose). Writes only the plan artifact.

## Envelope
- **Tool posture:** read-only **plus** write scoped to the plan path (e.g. `docs/plans/`). No source edits.
- **Context gathering:** broad → converge (explore widely, then narrow to a decision).
- **Policy blocks:** action-default Side B (`do_not_act_before_instructions`) + context-gathering (broad) + self-reflection (self-critique vs. constraints). No persistence/action blocks.
- **Verification:** self-critique against the stated constraints, **then a user approval gate** — the plan is a proposal, not a mandate.

## Output / handoff
Emits `docs/plans/<slug>.md`: goal, 2–3 alternatives with trade-offs, steps, risks, definition-of-done. This is the plan stance's own task pattern (`patterns/planning`). Consumes: the task + explore notes. Followed by **implement** (which consumes the approved plan and does not re-plan).

## Routing — entering / leaving
- **Enter when:** the task would touch more than ~3 files, add a dependency, or make an architecture decision (modes §5 rule). Also the explore→plan→code discipline: decide before building.
- **Leave when:** the plan is approved → implement it. If an approved plan already exists for the task, skip planning and implement.
- **Continuous re-routing:** a mid-session redirect re-routes immediately; acknowledge the switch. Explicit invocation is the top signal (M7); a harness-enforced mode supersedes it (M3).

## Enforcement (plan-artifact-only writes)
- **Claude Code:** `allowed-tools` scoped to read/grep + write to the plan path; PreToolUse hook.
- **Codex:** approval rules gating writes; sandbox scoped.
- **Fallback (any harness):** prose block + explicit path allowlist naming the one writable location.

Emit both the config and the prose gate; prose-only is the degraded mode.
