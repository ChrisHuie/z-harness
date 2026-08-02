# Provenance gate (v2) — ADDENDUM to RUBRIC.md. Read RUBRIC.md first, then this.

This addendum OVERRIDES RUBRIC.md wherever they conflict. It applies to all memories
outside the salesagent silo.

## The problem this exists to prevent

Chris confirmed: most non-salesagent projects are dormant (touched once every few
months, several never revisited), and their memories were produced by **much less
robust agents** than the ones that wrote salesagent's. Those memories are NOT of
equal quality, and must not be treated as equal evidence.

Promotion is **asymmetric risk**. A weak rule left in a dormant silo harms nothing —
nothing loads it. A weak rule promoted to `~/.claude/CLAUDE.md` loads into EVERY
session including salesagent, and actively degrades Chris's best-maintained setup.

**Therefore: the default disposition for every memory you review is LEAVE-IN-PLACE.**
Promotion is the exception that must be argued for, not the goal.

## Measured trust tiers — use these, do not re-derive

| Trust | Projects | Evidence |
|---|---|---|
| **HIGH** | `salesagent` (169 mem / 159 sessions), `prompt-harness` (5 / 124) | Repeatedly exercised; survived contact with reality |
| **MEDIUM** | `rereview-agent` (6/4), `hermes-plan` (2/6), `-Users-quantum` (3/3) | Some real use, limited re-validation |
| **LOW** | `agentic-prebid` (33 mem / **3 sessions** = 11 per session), `prebid-agent-skills` (12/2), `norbert-skills` (7/2) | Written in bulk, never revisited |
| **LOWEST** | `agentic-advertising`, `adcp-tooling`, `ComputedChaos-skills`, `github-activity-db`, `prebid-github-io`, `project-plugins` | **Zero surviving sessions.** Written once, never used again |

## The promotion gate

A memory from a non-HIGH silo may be proposed for **T1-UNIVERSAL** only if it clears
one of these. State which gate it cleared in `why`:

- **(a) CORROBORATED** — a HIGH-trust memory states substantively the same rule. Name
  that file. This is the strongest and preferred path.
- **(b) INDEPENDENTLY VERIFIED** — you confirmed the underlying claim yourself from
  primary sources (read the code, ran the command, checked the spec). Put exactly what
  you did in `verified`. "It sounds right" is not verification.
- **(c) SELF-EVIDENT ABOUT CHRIS** — a plain fact about Chris's identity, permissions,
  or stated preferences that cannot really be wrong (e.g. who owns `git push`).

**If it clears none of these, the tier is `LEAVE-IN-PLACE`.** Not T1, not T2 — leave it
exactly where it is and move on. This is the correct and expected outcome for most
low-trust memories. Do not stretch to promote things.

**T2-DOMAIN** from a LOW/LOWEST silo needs gate (a) or (b) as well. Same reasoning: the
domain file loads into ~10 active prebid repos.

## Extra scrutiny for the LOW/LOWEST tiers

These memories were written by weaker agents. Actively look for:
- **Overconfident claims with no cited evidence** — assertion where a trace is needed.
- **Fabricated specifics** — file paths, line numbers, function names, or PR numbers
  that do not exist. CHECK them. This is the single most common weak-agent failure.
- **Over-generalization from one incident** — a one-off framed as a universal law.
- **Stale-by-construction** — describes a plan or intent that was never carried out.

If a memory fails on any of these, mark it `STALE` or `LOW-QUALITY` and say precisely
what you checked and what you found. Do not soften it.

## Output — same JSON schema as RUBRIC.md, with these additions

Add to every object:

```json
{
  "trust": "HIGH | MEDIUM | LOW | LOWEST",
  "gate_cleared": "a-corroborated | b-verified | c-self-evident | none",
  "corroborating_memory": "<HIGH-trust filename, or null>",
  "quality_flags": ["overconfident" | "fabricated-specifics" | "over-generalized" | "stale-by-construction"]
}
```

`tier` may now also be `LEAVE-IN-PLACE`, and for most of these it should be.
