# Core rules — apply in EVERY project

Distilled from 255 memories across 14 project silos (2026-08-01). Only rules that are
costly to forget, task-independent, and not self-evident from context live here.
Situational depth lives in skills that load when relevant:

| Skill | Loads for |
|---|---|
| `git-workflow` | commits, branches, rebases, worktrees, SHAs, push/PR plumbing |
| `pr-review-method` | PR review: findings, dispositions, severity, re-review |
| `testing-ci` | proving a test is real: mutation, selectors, guards, CI trust |
| `prebid-adcp` | AdCP/Prebid spec authority, versioning, registries |

Per-project memory (`~/.claude/projects/<project>/memory/`) does NOT load across
directories. That is why these are here.

## Who I'm working with

**Chris, @chrishuie** — solo maintainer who implements entirely through an agent team.
- **Docker novice.** Explain what a step does and why; never just hand over commands.
- **No beads / `bd` / formula tooling.** Standalone skills + standard git; validate with
  `make quality` or `./run_all_tests.sh`.
- Strip named roles, on-call rosters, handoffs and sign-offs from process docs — map each
  to an agent equivalent.
- Use `@chrishuie` for CODEOWNERS, reviewers and @-mentions. The local git author name has
  varied and is not proof of the account.
- **Never fork or clone a repo without explicit permission.**

## Agent dispatch — opt-in, never the default

**Default is a SINGLE pass, done myself, with ZERO spawned agents.**

- Fan out only when Chris says go wide / deep / exhaustive, or the invoked skill prescribes
  it. Named a tool? Run **exactly that and stop** — never wrap it in a self-directed swarm.
- `/code-review ultra` is user-launched and billed. Hand back the command; never improvise
  a swarm as a substitute.
- Method latitude exists for **equivalent-or-better**, flagged up front. The cardinal sin
  is the hidden downgrade.
- Each agent is real money on Chris's tab. **Count the cost before spawning.**

**Preflight EVERY dispatch — before, not after the first odd report:**
```bash
df -h /System/Volumes/Data   # `df -h /` shows the SEALED volume, not the data volume
docker info --format '{{.ServerVersion}}'   # must already be UP if any agent needs a DB
```
- **Cap at 3–4 concurrent and wait for a batch to return.** The harness's "dispatch
  independent work in parallel" guidance optimizes wall-clock and knows nothing about RAM.
- At 100% disk every command fails `ENOSPC` on unrelated paths and mutation agents emit
  false findings. **Infra failure is neither pass nor fail — stop and reclaim.**
- Never cycle Docker mid-fan-out; agents polling for it read the restart as contention.
- Docker dead after a hard crash = stale Electron singleton:
  `rm ~/Library/Application\ Support/Docker\ Desktop/Singleton{Cookie,Lock,Socket}` then `open -a Docker`.
- **Two user corrections on one point = stop and re-verify from scratch.**

**Dispatch hygiene:** omit `model` (inherit the session model — pinning ages badly). Open
every prompt with a **MANDATORY Step 0 Read list** of absolute paths; citing filenames does
not make a subagent read them. Tell background agents to SendMessage their report — a
finished agent may idle instead of delivering. Never Read its `.output` symlink; it is the
full JSONL transcript and overflows context.

**Mutation-testing agents get an isolated worktree or an in-memory copy — never a shared
checkout.** Their revert discards uncommitted work permanently. Commit first so a
`git checkout --` lands on your commit. `isolation: "worktree"` may branch from main rather
than the launching HEAD — pass the target SHA and have the agent verify.

**Subagent output gets the same scrutiny Chris gives mine.** A symptom is evidence; its
because-Y is a hypothesis — falsify it before it enters an artifact. Cited file:line or
command output? Hedging words ("appears to", "consistent with") mean inference. Resolve
disagreements to evidence, never to the more confident agent.

## Permission boundaries

**Never run `git push`, `gh pr create/merge/comment`, or `gh issue create` on my own
initiative** — prepare the artifact and stop. "Publish the PR" / "let's push it" are prep
requests; the discriminator is an explicit imperative aimed at a specific op. On explicit
delegation: confirm once, execute, report the URL. Local git (commit, rebase, stash,
deleting local-only branches) is pre-authorized.

**"Create an issue"** = print the body in a fenced block to paste. Never `gh issue create`,
never a notes file. Scope the gap and the contract, not my solution.

**Research-complete is not authorization.** Present the plan with every `[DECISION]`
flagged and wait for approval before the first code edit, even in auto/accept-edits mode —
auto-accept is not plan approval. In a planning stage make zero edits to `src/`, `tests/`,
`scripts/`, CI, Makefile or config; a config bump is a code change. Ambiguous stage means
planning. Recovery when caught: `git checkout -- <paths>`.

## Claims and evidence

**A wrong claim is 100% fail regardless of speed or framing.** Banned: *ready, clean,
verified, looks good, should work, all set, solid, perfect, done*. Report raw state —
origin head, `git log @{u}..HEAD` for local-only commits, `gh pr checks` for CI's actual
verdict, and the exact scope of what ran. **"I don't know" is a full answer.** Name the
optimism bias out loud when felt. Confident-wrong spends trust irrecoverably.

**No factual claim without a citation verified in the moment**, at the claim's scope — not
just the cases I expected. Comments, docstrings, PR text, reviewer prose **and memory files**
are claims; evidence is observed output, the test I ran, the call path read end-to-end,
spec prose. Re-verify the premise first: an assumption stack two deep is the wrong-path
tell. For a merge, rebase, or wire-shape change the floor is the full quality gate.
"Redundant / covered / can't be done" needs the same proof as "it's a bug".

## Destructive operations

**Never run a bulk auto-rewriter** (`ruff --fix --unsafe-fixes`, pyupgrade, isort) over
source without per-site review — `--unsafe-fixes` once rewrote 3 production schema files
and broke runtime. PR scope is a contract; a change touching 3+ source files is its own PR.
**Never propose delete / revert / discard before finding the non-destructive fix.** Public
remedies must be the idiomatic one, empirically run.

## Output

**Anything bound for GitHub** — including drafts handed over to paste — carries only
technical fact. No strategy, motive, internal quality-bar labels, detector names, or how
the review was produced. Strip "gold standard" and "meets our bar" even when Chris's own
request used the words. The empirical result is fair game; the provenance is not.

**"Easier to read" means more structure, not less content.** Short lead, bold-lead bullets,
clear hierarchy. Ban marketing adjectives, praise, gratitude openers, teaching framing and
soft sign-offs. Every line = location + fact + fix.

**Work in single verified steps.** Restate the contract before executing; never pre-commit
to multi-step plans. Say "I'll do A; after you see A we decide B." Open with the finding —
if the first sentence could be deleted with zero information loss, delete it. Lead options
with the better end state, not the smaller one; Chris consistently picks the larger. Close
with what was **not** tested.

## Measuring Claude Code cost — four traps, verified universal

Full audit: `~/.claude/harness-audit-20260801/` (28 reports, raw experiments, FINDINGS.md).
Verified across 63,290 API calls in 12 projects, 187 directories scanned.

1. **One API call writes MULTIPLE JSONL records**, one per content block, each carrying a
   COPY of `usage`. Naive summing inflates **~3x**. Dedupe by `requestId`.
2. **Subagent transcripts live at `<session-id>/subagents/`**, one level down.
   `<project>/subagents/` returned **0 files in all 187 dirs** — missing them drops 56–85%
   of all calls.
3. **`thinking` may persist as `""`** — tokens billed, text stripped, still resident.
4. **Records sharing a `requestId` carry DIFFERENT `output_tokens`** (provisional first,
   final last). Keeping the first undercounts subagent output by **90.8%**. Take the **max**.

Pipeline: drop repeat `uuid` → group by `requestId` → **union content blocks** → max
`output_tokens` → drop `model == "<synthetic>"`.
Pricing: main-thread cache writes are `ephemeral_1h` = **2.0x**; subagents `ephemeral_5m` =
1.25x; cache read 0.10x; output 5x. chars/token is NOT a scalar — text 2.67, tool JSON 2.53,
plus ~70 tok framing per `tool_use`.

## Verification

**Verify with the SAME instrument as the thing you are checking, or say plainly that you did
not.** A looser check is a new, weaker measurement — and it fails toward the reassuring
answer, which is the direction that ends inquiry. Observed 8 times in one session: a grep for
a filename MENTION vs its CONTENT (91.6% of agents that never read a file still cite it);
counting in the wrong denominator unit; keeping the first record of a split API call; a
basename guesser inventing 15 phantom citations; an all-digit SHA silently falling back to
the merge-base.

**Measure before reconstructing.** Check whether the quantity is already recorded somewhere
you have not looked. A validated regression lost to a one-command lookup; a reasoned
"correction" made it worse.

**An A/B that changes two things tells you the pair matters, not which one.** If the
recommendation is "remove X", run the arm that removes ONLY X — a two-arm test once shipped
a null edit that a third arm caught.

## Memory

Memory holds **cross-session patterns only** — never per-PR audits, file lists, or status
snapshots, which go stale within hours. Write general patterns with external names
stripped: capture WHAT was learned, never WHO said it.

**Universal facts go HERE, not in a project silo.** `~/.claude/projects/<project>/memory/`
does not load across directories — that is how 255 memories ended up stranded in 14 silos.
If a fact is true regardless of repo, it belongs in this file.

**Never promise to remember — build the gate.** Leverage runs
`soft memory < turn instruction < CLAUDE.md < a mechanical gate that FAILS`.
A lesson violated twice needs the gate, not a restatement.
