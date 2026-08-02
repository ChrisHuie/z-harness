---
name: agent-dispatch
description: Running work in parallel agents - how many to launch, what to check before launching, and how much of what comes back to believe. Use before spawning agents or fanning out, when one agent will edit files another is reading, when a background agent finishes without delivering its report, and before repeating an agent's explanation as fact.
---

# Dispatching agents

## The preflight cannot live here

A skill body loads at **turn 1 of the agent that loads it** — after the parent already
spawned — and an agent whose `tools:` allowlist omits `Skill` gets neither the tool nor
the listing. **A preflight written as prose is a reminder, not a gate.** Put it in a
`PreToolUse` hook in `~/.claude/settings.json` on the spawn tool (matcher `Agent|Task`;
this harness emits `Agent`), exiting non-zero to block. The append-to-subagent-system-prompt
flag pierces every nesting depth and is the only non-negotiables channel headless; hooks
see the agent type, so per-depth capture is free.

## Before you spawn

- **Budget is window-expiring, so its value is time-varying** — scarce mid-window, ~0 at
  reset. Surface the estimate and window position; near reset drain the parked queue.
- **Subagents don't inherit the main thread's cache prefix** — a third start at zero, so
  an N-per-item fan-out re-reads the same files N times at full price. Batch by shared
  context.
- **Assign by derivative chain and seam, not file or dimension** — a defect on the seam
  between two dispatched dimensions is owned by neither.
- **A status-clean check between another agent's edit and its restore still races** —
  "revert then verify clean" *is* the collision path, not the fix. Worst when the target is
  a guard every specialist mutates.
- **Demand a baseline assertion before every mutation** — clean status plus a green exit,
  stop-and-report on mismatch.

## The prompt

- **A subagent inherits nothing** — not system prompt, style, or history; skipping the
  context files hands the child a *default identity*.
- **Reference-first transport**: a bounded manifest of absolute paths plus *why each is
  authoritative*. Never paste diffs or file bodies in.
- **State the stage** — "planning: spec only" / "implementation approved"; it is not
  inherited.
- **Frame each hypothesis to refute, not confirm** — require `file:line` plus an attempted
  refutation per finding.
- **Fix the report contract up front**: observation-vs-inference labels and an explicit
  "what I did NOT verify" list. Confidence with no sample size is not a measurement.

## Grading what comes back

- **Resolve a disagreement between agents to evidence, never to the more confident one** —
  cited `file:line` or command output is evidence; hedging (*appears to*, *consistent with*)
  marks inference.
- **A synthesizer cannot red-team their own synthesis** — its fixes read correct by
  mirroring the hardened prose. Observed 7×, recursion included.
- **No agent writes, or supplies the input to, the instrument that grades it** — did the
  checked party author the commands, and does exit 0 discriminate anything?
- **Forbid a cross-verify agent from reading the others' work** — it corroborates
  instead of checking.
- **Fresh context ≠ fresh gradients** — tendencies are weight-level, so a same-family
  observer shares a common-cause failure. Independence needs a different model *family* —
  a diversity axis, not the pinning axis.
- **Power-validate the instrument before believing a null** — seed known flaws and require
  recall ≥2/3 or discard the nulls, freeze the novelty criterion before the run, never let
  the claimant author the acceptance criterion. Strongest claim: "power-validated
  independent search found nothing."
- **Audit a modifying agent with a second agent** whose only job is that audit, on its own
  Step-0 read list — the load-bearing variables are the explicit READ and fresh context.
- **One measured cell is a hypothesis about the rest of the matrix** — over-generalizing a
  single endpoint's reliability once fabricated a figure.
- **Rounds converge to finer shades, not zero** — "zero findings" never terminates. Stop
  on monotonically decreasing findings or a severity floor, and re-trace after heavy
  edits: a convergence pass catches what your fixes introduced.
- **Three lenses once a fan-out is authorized**: a critic (end-to-end, severity-ranked) ·
  a freshness verifier (re-pull every cited anchor) · a completeness checker (read every
  source the artifact claims to distil, name what was lost). Synthesize yourself; never
  relay a delegate's output as a recommendation.

## When it goes wrong

- **Ping a stalled agent; never re-spawn** — its transcript is intact, and a ping is a
  second chance to aim: re-ask the contested question, add what you since verified, say
  what *not* to re-derive.
- **Transcript-only work must stream to a durable file as produced**, or the largest
  surviving artifact is evidence about itself. After a crash, `*.meta.json` with no
  `agent-*.jsonl` means those transcripts are gone; a ~100 B parent is the tell.
- **Orphaned children hold pipes open past a kill**, so the parent's read never returns —
  kill the process *group*.

**Read `references/deferred.md` first if the dispatch involves agent-system design, a
capability ceiling, per-tier power validation, or a reclaim order.**
