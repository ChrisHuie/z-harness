# Arbitration rubric (v3) — routing 109 candidate rules into a real structure

## What happened, and why you exist

Three agents classified 169 salesagent memories against a rubric whose only "universal"
bucket was `T1-UNIVERSAL`. They disagreed by 3x — 72% / 82% / 27% — and between them
proposed **103 rules for an always-loaded file**. That is ~176 lines of bare one-liners
before any rationale, which would bury the rules that actually matter.

The rubric was at fault, not the agents. It had no bucket for Chris's **workflow
practice** — rules that span all his repos but are neither universal engineering fact nor
domain knowledge — so those got forced into `T1`. You are re-routing all 109 with buckets
that fit.

## Your buckets

**CORE** → `~/.claude/CLAUDE.md`, loaded in EVERY session in EVERY directory.
**HARD CAP: 20 rules. Treat 15 as the target.** A rule earns CORE only if ALL hold:
1. **Costly to forget** — forgetting it wastes real money, destroys work, breaks trust,
   or crosses a boundary Chris owns. (The incident that triggered this project: 12 agents
   dispatched at once froze his machine and lost work.)
2. **Task-independent** — applies whether the session is git, research, writing, or code.
3. **Not self-evident from context** — I would not naturally do it by reading the code.

If a rule is important but only matters *while doing a specific kind of work*, it is NOT
core. It belongs in a skill, which loads exactly then. Being in a skill is not demotion.

**SKILL:git-workflow** → git/gh mechanics: commits, branches, rebases, worktrees, SHAs,
push/PR plumbing, `git grep`/`git mv` gotchas.

**SKILL:review-practice** → how Chris runs PR review: findings, dispositions, severity,
re-review, merge recommendations, what may be claimed and when.

**SKILL:testing-ci** → tests, CI, mutation testing, coverage, structural guards, oracles.

**SKILL:prebid-adcp** → Prebid/AdCP domain: specs, protocol facts, versioning, registries.

**DEMOTE-T3** → actually specific to one repo's code/paths/CI. Goes back to the salesagent
silo. Expect a real number of these; two of the three agents were over-promoting.

**DROP** → semantically duplicates another candidate. Name the winning `id` in
`duplicate_of` and say why that one wins. The three work lists were disjoint, so there are
no file-level duplicates — but the SAME RULE is often written up in several memories.
Merge aggressively; a merged rule should state the union of what the copies knew.

## Ranking

Give every rule `cost_of_forgetting` 1–5:
- **5** — destroys work, burns significant money, or crosses a boundary Chris owns
- **4** — produces a confidently wrong claim or a silently broken artifact
- **3** — wastes a cycle; recoverable
- **2** — mild inefficiency or style
- **1** — trivia

CORE should be drawn almost entirely from 5s and 4s. If you have more than 20 rules at 4–5,
put the strongest 20 in CORE and route the rest to skills — say in `why` that you did.

## Non-negotiable constraints

- **80 of the 109 are flagged `harness_critical: true`** — they support Chris's salesagent
  review harness, which is load-bearing and must not be degraded. Routing one to a skill is
  fine (it still loads when relevant). **DROPPING or DEMOTING a harness-critical rule needs
  an explicit, specific justification** in `why`. When genuinely unsure, keep it.
- **Preserve meaning when you merge.** A merged rule must not be vaguer than its parts.
  Specific commands, flags, and failure modes are the value — keep them verbatim.
- **You are READ-ONLY.** Do not create, edit, move, or delete any file. You return JSON.
- Do not invent rules. Every output must trace to input `id`s.

## Input

`/private/tmp/claude-501/-Users-quantum-Documents-GitHub-agenticads-sim-plan/e2367c8b-0c8b-43ae-a5d4-98ce3fbcecea/scratchpad/arbitration-input.json`
— 109 objects with `id`, `source_agent`, `proposed_tier`, `file`, `name`, `one_line`,
`why`, `harness_critical`, `confidence`.

Read the original memory `file` for any candidate whose `one_line` is ambiguous, or before
dropping/demoting anything harness-critical. Do not decide those from the summary alone.

## Output — return ONLY this JSON object

```json
{
  "rules": [
    {
      "ids": [<input ids merged into this rule>],
      "bucket": "CORE | SKILL:git-workflow | SKILL:review-practice | SKILL:testing-ci | SKILL:prebid-adcp | DEMOTE-T3 | DROP",
      "rule": "<imperative statement, <=200 chars, keeps specific commands/flags>",
      "detail": "<mechanism + why it matters, <=400 chars, or null>",
      "cost_of_forgetting": 1-5,
      "harness_critical": true|false,
      "duplicate_of": <id or null>,
      "why": "<why this bucket; for DROP/DEMOTE of harness-critical, justify specifically>"
    }
  ],
  "core_count": <int, MUST be <= 20>,
  "disagreement_notes": "<where mem-sa-a/b/c most disagreed and how you resolved it>",
  "coverage_check": "<confirm all 109 input ids appear in exactly one rules[].ids>"
}
```

`coverage_check` is mandatory: every one of the 109 ids must appear exactly once. Verify
before returning.
