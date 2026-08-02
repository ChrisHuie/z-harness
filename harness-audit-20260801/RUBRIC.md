# Memory tier-classification rubric (v1) — READ THIS FIRST, IN FULL

You are classifying Claude Code memory files into a three-tier context structure for
Chris (@chrishuie), a solo maintainer in the Prebid / AdCP advertising ecosystem.

## The three tiers

**T1-UNIVERSAL** → destined for `~/.claude/CLAUDE.md`, loads in EVERY session in EVERY
directory. Reserve for rules true regardless of repo, language, or domain: facts about
Chris himself, how the agent should work, cost/permission/safety boundaries.
> Test: "Would this still be true if Chris started a brand-new, unrelated project
> tomorrow — a Rust game engine, say?" If yes → T1.

**T2-DOMAIN** → destined for `~/.claude/shared/prebid-adcp.md`, imported by the repos
that need it. For rules true across the Prebid + AdCP repos but NOT universal: spec
conventions, AdCP versioning, adagents.json, ecosystem review etiquette, cross-repo
protocol facts.
> Test: "Is this true in salesagent AND agentic-prebid AND Prebid.js, but meaningless in
> an unrelated Python repo?" If yes → T2.

**T3-REPO** → stays in its project silo. Tied to one repo's code, paths, CI, schema,
ports, or test layout.
> Test: "Does this name a specific file, function, table, port, env var, or CI job that
> exists in exactly one repo?" If yes → T3.

## Two disqualifying states — check BOTH before assigning a tier

**STALE** — the memory references something that no longer exists, or a newer memory
supersedes/contradicts it. You MUST verify, not assume. If a memory names a file,
function, flag, PR, or path, check whether it still exists (`ls`, `git grep`, `gh`).
Report the exact evidence that makes it stale. A memory that is merely OLD is not stale.

**DUPLICATE** — another memory states substantively the same rule. Name the twin's
filename. Prefer keeping the more specific/better-evidenced one; say which and why.

## Critical constraints

- **READ-ONLY. Do not edit, move, or delete ANY file.** You produce analysis only.
- **Chris's salesagent review harness is load-bearing and must not be degraded.** If a
  memory supports `/code-review`, the review harness, or anything in
  `.claude/skills/`, flag `harness_critical: true` even if it looks duplicated. Those
  get human review before any change.
- **Comments and memory text are CLAIMS, not evidence.** If a memory asserts "X is
  configured to do Y", verify against the actual file/code before endorsing it.
- Rules about how the agent works (fan-out, cost, permissions, asking) are almost always
  T1 even when written inside a project silo — that misfiling is the whole reason for
  this task.

## Output — return ONLY a JSON array, no prose before or after

```json
[
  {
    "file": "<absolute path>",
    "name": "<name: field from frontmatter>",
    "type": "<metadata type: field>",
    "tier": "T1-UNIVERSAL | T2-DOMAIN | T3-REPO | STALE | DUPLICATE",
    "confidence": "high | medium | low",
    "one_line": "<the rule in <=140 chars, imperative voice, no hedging>",
    "why": "<why this tier, referencing the test above, <=200 chars>",
    "harness_critical": true|false,
    "duplicate_of": "<filename or null>",
    "stale_evidence": "<what you checked and what you found, or null>",
    "verified": "<what you actually ran/read to confirm, or null>"
  }
]
```

Be decisive. Use `low` confidence sparingly and say why in `why`. If a memory is long
and covers several rules, classify by its DOMINANT rule and note the split in `why`.
